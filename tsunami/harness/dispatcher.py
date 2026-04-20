"""Overnight dispatcher — launches N workers, monitors health, shuts down.

Thin wrapper around subprocess.Popen for N worker.py instances plus a
poll loop that checks SIGMA_AUDIT §17.7 kill-switch triggers. Not a
full scheduler — workers self-pull from matrix.jsonl via fcntl lock
(see worker._acquire_row). Dispatcher's role is: start N workers,
watch for triggers, reap on exit.

Usage:
    python -m tsunami.harness.dispatcher \
        --root ~/.tsunami/overnight \
        --workers 4 \
        --dry-run          # worker.py --dry-run per worker

Kill triggers per §17.7:
  - worker_dead_loop    : worker subprocess exited non-zero ≥3 times
  - dispatcher_wedged   : runs.jsonl hasn't grown in 30 min
  - disk_pressure       : --root usage > 30 GB
  - llama_server_down   : not implemented here (workers handle it)
  - runaway_cost        : not implemented (external cost_tracker reads)
  - retraction_spike    : not implemented (needs live retractions.jsonl)
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
WORKER_SCRIPT = REPO / "scripts" / "overnight" / "worker.py"


def _iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _dir_bytes(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except Exception:
            continue
    return total


def _count_runs(root: Path) -> int:
    runs = root / "runs.jsonl"
    if not runs.is_file():
        return 0
    with runs.open() as f:
        return sum(1 for _ in f)


def _matrix_size(root: Path) -> int:
    m = root / "matrix.jsonl"
    if not m.is_file():
        return 0
    with m.open() as f:
        return sum(1 for _ in f if _.strip())


def launch_workers(root: Path, n: int, dry_run: bool) -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    for i in range(n):
        wid = f"worker_{i+1:03d}"
        cmd = [sys.executable, str(WORKER_SCRIPT),
               "--id", wid, "--root", str(root)]
        if dry_run:
            cmd.append("--dry-run")
        print(f"[dispatcher] launching {wid}: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, preexec_fn=os.setsid)
        procs.append(proc)
    return procs


def reap(procs: list[subprocess.Popen], signum: int = signal.SIGTERM) -> None:
    for p in procs:
        if p.poll() is None:
            try:
                os.killpg(os.getpgid(p.pid), signum)
            except Exception:
                pass


def poll_loop(root: Path, procs: list[subprocess.Popen],
              wedge_timeout_s: int = 1800,
              disk_cap_gb: int = 30,
              dead_exit_cap: int = 3,
              poll_interval_s: int = 30) -> str:
    """Watch workers and trigger conditions. Returns exit reason."""
    last_run_count = _count_runs(root)
    last_grow_ts = time.time()
    dead_exits = 0

    try:
        while True:
            # 1. Worker process health
            alive = [p for p in procs if p.poll() is None]
            exited = [p for p in procs if p.poll() is not None]
            for p in exited:
                if p.returncode != 0:
                    dead_exits += 1
            if not alive:
                return "all_workers_exited"
            if dead_exits >= dead_exit_cap:
                reap(procs)
                return "worker_dead_loop"

            # 2. Dispatcher wedge — no runs.jsonl growth for N seconds
            cur = _count_runs(root)
            if cur > last_run_count:
                last_run_count = cur
                last_grow_ts = time.time()
            elif time.time() - last_grow_ts > wedge_timeout_s:
                reap(procs)
                return "dispatcher_wedged"

            # 3. Disk pressure
            bytes_used = _dir_bytes(root)
            if bytes_used > disk_cap_gb * 1024**3:
                reap(procs)
                return f"disk_pressure_{bytes_used // 1024**3}gb"

            # 4. Matrix drained? If all rows claimed AND all workers idle
            # (exited cleanly), we're done.
            matrix = _matrix_size(root)
            if matrix > 0 and cur >= matrix:
                # Let workers drain their last in-flight row.
                time.sleep(poll_interval_s)
                if all(p.poll() is not None for p in procs):
                    return "matrix_drained"

            time.sleep(poll_interval_s)
    except KeyboardInterrupt:
        reap(procs)
        return "interrupted"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wedge-timeout-s", type=int, default=1800)
    parser.add_argument("--disk-cap-gb", type=int, default=30)
    parser.add_argument("--poll-interval-s", type=int, default=30)
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    root.mkdir(parents=True, exist_ok=True)

    if not (root / "matrix.jsonl").is_file():
        print(f"ERROR: no matrix.jsonl at {root}. Run matrix_gen.py first.")
        sys.exit(2)

    print(f"[dispatcher] root={root} workers={args.workers} dry_run={args.dry_run}")
    print(f"[dispatcher] matrix has {_matrix_size(root)} rows")

    procs = launch_workers(root, args.workers, args.dry_run)
    reason = poll_loop(root, procs,
                       wedge_timeout_s=args.wedge_timeout_s,
                       disk_cap_gb=args.disk_cap_gb,
                       poll_interval_s=args.poll_interval_s)
    print(f"[dispatcher] shutdown: {reason}")
    # Final reap — make sure nothing's lingering.
    reap(procs, signal.SIGTERM)
    time.sleep(2)
    reap(procs, signal.SIGKILL)

    runs = _count_runs(root)
    print(f"[dispatcher] final: runs={runs}/{_matrix_size(root)} reason={reason}")


if __name__ == "__main__":
    main()
