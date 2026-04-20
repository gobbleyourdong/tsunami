"""Overnight worker — claim a row, run tsunami, probe, emit telemetry.

Runs as a long-lived loop:
  1. Claim next row from matrix via dispatcher fcntl lock
  2. Build env + subprocess args for this row
  3. Exec tsunami (or `echo` in --dry-run) under budget_s timeout
  4. On message_result: run probe, write telemetry
  5. Append runs.jsonl row
  6. Loop

Never modifies tsunami's agent.py — runs it as a black-box subprocess.
Workers share the `:8090` llama-server; isolation via per-worker
deliverable dir (TSUNAMI_WORKSPACE_DIR) so dist/ folders don't
collide. Probe is F-B1/F-I4 from tsunami/harness/probe.py.

Usage:
    python -m tsunami.harness.worker \
        --id worker_001 \
        --root ~/.tsunami/overnight \
        --dry-run        # use `echo` instead of tsunami for plumbing tests
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Make tsunami importable for the probe.
REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami import content_probe as _probe  # noqa: E402


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _acquire_row(root: Path, worker_id: str) -> dict | None:
    """Claim the next unclaimed row from matrix.jsonl using fcntl.

    Returns the row dict, or None if the queue is drained.

    Implementation: read matrix.jsonl + claimed.jsonl each time under
    lock, pick the first row whose run_id isn't in claimed, append to
    claimed.jsonl, release lock, return row.
    """
    matrix_path = root / "matrix.jsonl"
    claimed_path = root / "claimed.jsonl"
    lock_path = root / "matrix.lock"
    claimed_path.touch(exist_ok=True)
    lock_path.touch(exist_ok=True)

    with lock_path.open("r+") as lock_fp:
        try:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
            claimed_ids: set[str] = set()
            with claimed_path.open() as f:
                for line in f:
                    try:
                        claimed_ids.add(json.loads(line)["run_id"])
                    except Exception:
                        continue
            with matrix_path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("run_id") in claimed_ids:
                        continue
                    # Claim it.
                    with claimed_path.open("a") as cf:
                        cf.write(json.dumps({
                            "run_id": row["run_id"],
                            "worker": worker_id,
                            "ts": _iso_now(),
                        }) + "\n")
                    return row
            return None
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)


def _run_tsunami(row: dict, worker_dir: Path, dry_run: bool) -> dict:
    """Run tsunami (or echo) under budget_s timeout. Return outcome."""
    run_id = row["run_id"]
    deliverable_dir = worker_dir / "deliverables" / run_id
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    session_log = worker_dir / "sessions" / f"{run_id}.log"
    session_log.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(row.get("env", {}))
    # Point tsunami at the worker-specific workspace.
    env["TSUNAMI_WORKSPACE_DIR"] = str(worker_dir)
    env["TSUNAMI_TELEMETRY_DIR"] = str(worker_dir.parent.parent / "telemetry")

    budget = int(row.get("budget_s", 600))
    started = time.time()
    exit_reason = "unknown"
    returncode = None

    if dry_run:
        # Simulate a tsunami run — write a fake App.tsx into the
        # deliverable, claim message_result exit.
        cmd = ["bash", "-c", (
            f"mkdir -p {deliverable_dir}/src && "
            f"echo 'import {{ CameraFollow }} from \"@engine/design/catalog\";' "
            f"> {deliverable_dir}/src/App.tsx && "
            f"sleep 0.2"
        )]
    else:
        # `python -m tsunami --task <prompt> --workspace <worker_dir>`
        # must run from the repo root so the package imports. REPO is
        # resolved at module import from tsunami/harness/worker.py's
        # location; override by passing TSUNAMI_REPO env.
        repo = os.environ.get("TSUNAMI_REPO") or str(
            Path(__file__).resolve().parent.parent.parent
        )
        cmd = [sys.executable, "-m", "tsunami",
               "--task", row["prompt"],
               "--workspace", str(worker_dir)]

    try:
        with session_log.open("w") as logf:
            logf.write(f"# run_id={run_id}\n# ts={_iso_now()}\n# cmd={cmd}\n")
            logf.flush()
            # For live mode, run from the repo root so `python -m
            # tsunami` resolves. For dry-run, cwd=worker_dir is fine.
            run_cwd = worker_dir if dry_run else Path(
                os.environ.get("TSUNAMI_REPO") or
                str(Path(__file__).resolve().parent.parent.parent)
            )
            proc = subprocess.Popen(
                cmd, env=env, stdout=logf, stderr=subprocess.STDOUT,
                cwd=str(run_cwd),
                preexec_fn=os.setsid,
            )
            try:
                returncode = proc.wait(timeout=budget)
                exit_reason = "message_result" if returncode == 0 else f"exit_{returncode}"
                # Round X post-mortem (2026-04-20): when the model server
                # was down, the wave got 5×"Model unreachable" errors, then
                # exited returncode=0 (shipped an empty message_result).
                # That misreports as a clean "message_result" delivery when
                # in fact no model call succeeded. Detect this and reclassify.
                if exit_reason == "message_result":
                    try:
                        log_text = session_log.read_text(errors="ignore")
                        # Count "Model unreachable" occurrences
                        unreachable_hits = log_text.count("Model unreachable")
                        # Heuristic: 3+ occurrences = systemic, not transient
                        if unreachable_hits >= 3:
                            exit_reason = "error:server_unreachable"
                    except Exception:
                        pass
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                time.sleep(2)
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                exit_reason = "timeout"
    except FileNotFoundError as e:
        exit_reason = f"error:{e}"
    except Exception:
        exit_reason = "error:unexpected"
        with session_log.open("a") as logf:
            logf.write("\n--- worker exception ---\n")
            logf.write(traceback.format_exc())

    wall_s = time.time() - started
    return {
        "wall_s": round(wall_s, 2),
        "returncode": returncode,
        "exit_reason": exit_reason,
        "deliverable_dir": str(deliverable_dir),
        "session_log": str(session_log),
    }


def _run_probe(row: dict, outcome: dict, root: Path) -> dict:
    """Run F-B1/F-I4 probe on the deliverable; write to telemetry/probes/.

    Swallows errors — probe failures should not block the worker.
    Returns a compact summary the runs.jsonl row embeds.
    """
    dv_dir = Path(outcome["deliverable_dir"])
    src_dir = dv_dir / "src"
    # Worker assumed tsunami would write under `deliverables/<run_id>/`,
    # but tsunami derives its own project name from the prompt (e.g.
    # "zelda-swiss" for "zelda-like top-down"). Also for gamedev, the
    # deliverable may NOT have src/ at all — emit_design writes
    # public/game_definition.json directly. Don't return `skipped`
    # when src/ is missing; gamedev_deliverable scan still has signal.
    if not src_dir.is_dir():
        try:
            workspace = dv_dir.parent.parent  # <worker_dir>
            siblings = sorted(
                [d for d in (workspace / "deliverables").iterdir()
                 if d.is_dir() and not d.name.startswith(".")],
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if siblings:
                candidate = siblings[0] / "src"
                if candidate.is_dir():
                    src_dir = candidate
                    dv_dir = siblings[0]
                else:
                    # No src/ but there's a recent deliverable dir —
                    # probe the deliverable root for gamedev artifacts.
                    dv_dir = siblings[0]
                    src_dir = siblings[0]  # probe.run handles non-src paths
        except Exception:
            pass
    # Allow probing non-src directories (gamedev deliverables). Only
    # truly-missing paths skip.
    if not (src_dir.is_dir() or dv_dir.is_dir()):
        return {"skipped": "no deliverable dir"}

    content_essence = row.get("expected_content_replica", "") or ""
    probe_out = root / "probes"
    probe_out.mkdir(parents=True, exist_ok=True)
    probe_path = probe_out / f"{row['run_id']}.json"

    try:
        report = _probe.run(src_dir, content_essence)
        probe_path.write_text(json.dumps(report, indent=2))
        content = report.get("content") or {}
        return {
            "mechanic_import_count": report.get("mechanic_import_count", 0),
            "generic_bleed_count": report.get("generic_bleed_count", 0),
            "content_named_distinct": content.get("named_distinct", 0),
            "content_adoption_rate": content.get("adoption_rate", 0.0),
            "probe_path": str(probe_path),
        }
    except Exception as e:
        return {"error": f"probe failed: {e}"}


def _append_run_row(row: dict, outcome: dict, probe_summary: dict, root: Path,
                    worker_id: str) -> None:
    """Append one row to runs.jsonl under a dedicated lock."""
    runs_path = root / "runs.jsonl"
    lock_path = root / "runs.lock"
    lock_path.touch(exist_ok=True)
    entry = {
        "run_id": row["run_id"],
        "ts_end": _iso_now(),
        "wall_s": outcome["wall_s"],
        "worker": worker_id,
        "row": row,
        "exit_reason": outcome["exit_reason"],
        "returncode": outcome["returncode"],
        "deliverable_dir": outcome["deliverable_dir"],
        "probe": probe_summary,
    }
    with lock_path.open("r+") as lock_fp:
        try:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
            with runs_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)


def worker_loop(worker_id: str, root: Path, dry_run: bool,
                max_rows: int = 0, sleep_on_empty: float = 10.0) -> int:
    """Main worker loop. Returns number of rows processed."""
    worker_dir = root / "workers" / worker_id
    worker_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    while True:
        if max_rows and processed >= max_rows:
            print(f"[{worker_id}] max_rows reached ({processed}); exiting")
            return processed
        row = _acquire_row(root, worker_id)
        if row is None:
            # Queue drained. On dry-run we stop; in live mode we wait
            # for the dispatcher to extend the queue (rare).
            if dry_run:
                return processed
            print(f"[{worker_id}] queue drained; sleeping {sleep_on_empty}s")
            time.sleep(sleep_on_empty)
            continue
        print(f"[{worker_id}] run {row['run_id']} — {row['prompt'][:60]}")
        outcome = _run_tsunami(row, worker_dir, dry_run)
        probe_summary = _run_probe(row, outcome, root)
        _append_run_row(row, outcome, probe_summary, root, worker_id)
        processed += 1
        print(f"[{worker_id}]   exit={outcome['exit_reason']} "
              f"wall={outcome['wall_s']}s probe={probe_summary}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--root", required=True, help="~/.tsunami/overnight/")
    parser.add_argument("--dry-run", action="store_true",
                        help="skip tsunami call; write fake App.tsx")
    parser.add_argument("--max-rows", type=int, default=0,
                        help="stop after N rows (0 = until drained)")
    args = parser.parse_args()
    root = Path(args.root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    n = worker_loop(args.id, root, args.dry_run, args.max_rows)
    print(f"[{args.id}] processed {n} rows")


if __name__ == "__main__":
    main()
