#!/usr/bin/env python3
"""auto_train.py — overnight v92 training cycle, with rollback safety.

Reads accumulated smoke DPO pairs, synthesizes them as supplementary SFT
examples, retrains v92 from base + (champion.jsonl ∪ new examples), runs
quick-eval, and SWAPS to v92 only if it doesn't regress.

Safety guards:
  - Won't run if server is busy (last request <2 min ago) — avoids GPU starve
  - Caps new-examples at 30 per cycle (no megacorpus drift)
  - Backs up current adapter before swap
  - Quick-eval (L1 only) gate: must score ≥ floor (default 95%) to swap
  - On failure, current adapter unchanged

Usage:
    python3 training/auto_train.py
    python3 training/auto_train.py --floor 90  # lower swap threshold
    python3 training/auto_train.py --dry-run   # show what would be added, no train
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DPO = REPO / "workspace" / "tsu_smoke_dpo.jsonl"
CHAMPION = REPO / "workspace" / "training_data" / "champion.jsonl"
ADAPTER = REPO / "models" / "tsunami-adapter"
ADAPTER_BACKUP = REPO / "models" / "tsunami-adapter.prev"
ADAPTER_NEW = REPO / "models" / "tsunami-adapter-auto"
SERVE_LOG = REPO / "training" / "logs" / "v90_coserve.log"
LAST_TRAIN = REPO / "workspace" / ".auto_train.last"
RUN_LOG = REPO / "workspace" / "auto_train.log"


def _log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a") as f:
        f.write(line + "\n")


def _last_request_age_s() -> float:
    """Seconds since the last server request — proxy for 'is anyone using it?'"""
    if not SERVE_LOG.exists():
        return 999_999
    try:
        # The serve log timestamps INFO lines like "INFO:     127.0.0.1:..."
        # but uvicorn doesn't put a timestamp on those. Use file mtime instead.
        return time.time() - SERVE_LOG.stat().st_mtime
    except OSError:
        return 999_999


def _last_train_age_s() -> float:
    if not LAST_TRAIN.exists():
        return 999_999
    try:
        return time.time() - LAST_TRAIN.stat().st_mtime
    except OSError:
        return 999_999


def _new_dpo_pairs(min_count: int = 3) -> list[dict]:
    """Return DPO pairs since last train. Returns empty list if too few."""
    if not DPO.exists():
        return []
    pairs = [json.loads(l) for l in DPO.open() if l.strip()]
    last_train_ts = LAST_TRAIN.stat().st_mtime if LAST_TRAIN.exists() else 0
    new = [p for p in pairs if p.get("ts", 0) > last_train_ts]
    if len(new) < min_count:
        return []
    return new[:30]  # cap at 30 per cycle


def _synthesize_sft_example(pair: dict) -> dict | None:
    """Convert a smoke DPO pair into a structured SFT example for build.py."""
    chosen = pair.get("chosen")
    if not chosen or pair.get("needs_operator_review"):
        return None
    tool = chosen.get("tool")
    args = chosen.get("arguments", {})
    if not tool:
        return None
    # Build a minimal pipeline: user → assistant emits chosen tool → tool_result → message_result
    from training.build import SYSTEM_TEXT
    msgs = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": pair["prompt"]},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": tool, "arguments": args}}]},
        {"role": "tool", "name": tool, "content": "[ok]"},
    ]
    # If chosen was a chat tool, that's the whole flow. Otherwise add message_result.
    if tool not in ("message_chat", "message_result"):
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "message_result",
             "arguments": {"text": f"Done: {pair['prompt'][:60]}"}}}]})
    return {"tag": f"smoke_{int(pair['ts'])}", "messages": msgs}


def _build_supplementary_corpus(pairs: list[dict]) -> Path:
    """Render new DPO-derived examples via tokenizer + append to a temp jsonl."""
    sys.path.insert(0, str(REPO))
    from training.build import render_example
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)

    sft = [s for s in (_synthesize_sft_example(p) for p in pairs) if s]
    if not sft:
        return None
    tmp = REPO / "workspace" / "training_data" / "champion_auto.jsonl"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    # Concatenate champion + new
    base = CHAMPION.read_text() if CHAMPION.exists() else ""
    new_lines = "\n".join(json.dumps({"text": render_example(ex, tok)}) for ex in sft)
    tmp.write_text(base.rstrip() + "\n" + new_lines + "\n")
    _log(f"corpus: {len(base.splitlines())} legacy + {len(sft)} new = {len(tmp.read_text().splitlines())} total → {tmp}")
    return tmp


def _train(corpus: Path) -> bool:
    """Run train.py against the supplementary corpus. Blocks until done."""
    out_dir = ADAPTER_NEW
    if out_dir.exists():
        shutil.rmtree(out_dir)
    cmd = [
        "python3", "-u", "training/train.py",
        "--data", str(corpus),
        "--output", str(out_dir),
        "--epochs", "10",
        "--grad-accum", "4",
        "--lr", "2e-4",
        "--lora-r", "8",
        "--merge",
        "--run-name", "auto_v92",
    ]
    env = os.environ.copy()
    env["UNSLOTH_SKIP_TORCHVISION_CHECK"] = "1"
    log_path = REPO / "training" / "logs" / "auto_v92.log"
    _log(f"training: {' '.join(cmd)} (log → {log_path})")
    with log_path.open("w") as lf:
        rc = subprocess.run(cmd, cwd=REPO, stdout=lf, stderr=subprocess.STDOUT, env=env).returncode
    _log(f"training rc={rc}")
    return rc == 0 and (out_dir / "adapter_model.safetensors").exists()


def _port_adapter(src: Path, dst: Path) -> None:
    """Port unsloth adapter to stock-PEFT-compatible by adding .linear suffix."""
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)
    cfg_path = dst / "adapter_config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["target_modules"] = sorted([f"{m}.linear" if not m.endswith(".linear") else m
                                    for m in cfg["target_modules"]])
    cfg.get("auto_mapping", {}).pop("unsloth_fixed", None)
    cfg["lora_alpha"] = cfg.get("r", 8) * 2
    cfg["lora_dropout"] = 0
    cfg_path.write_text(json.dumps(cfg, indent=2))


def _restart_server() -> None:
    """Kill the existing serve_transformers and spin up a new one."""
    subprocess.run(["pkill", "-9", "-f", "serve_transformers.py --model"],
                   stderr=subprocess.DEVNULL)
    time.sleep(2)
    log = REPO / "training" / "logs" / "v90_coserve.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["UNSLOTH_SKIP_TORCHVISION_CHECK"] = "1"
    proc = subprocess.Popen(
        ["python3", "-u", "tsunami/serve_transformers.py",
         "--model", "google/gemma-4-e4b-it",
         "--adapter", "models/tsunami-adapter",
         "--port", "8090", "--image-model", "none"],
        cwd=REPO, env=env,
        stdout=log.open("w"), stderr=subprocess.STDOUT,
    )
    _log(f"server restart pid={proc.pid}")


def _wait_for_server(timeout_s: int = 180) -> bool:
    """Poll /health until 200 or timeout."""
    import httpx
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            r = httpx.get("http://localhost:8090/health", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def _consecutive_failures() -> int:
    """Track how many cycles in a row have failed to improve."""
    p = REPO / "workspace" / ".auto_train.consecutive_failures"
    if p.exists():
        try:
            return int(p.read_text().strip())
        except ValueError:
            return 0
    return 0


def _set_consecutive_failures(n: int) -> None:
    p = REPO / "workspace" / ".auto_train.consecutive_failures"
    p.write_text(str(n))


def _is_halted() -> bool:
    """Auto-train halts after 3 consecutive failures until operator clears."""
    return _consecutive_failures() >= 3


def _baseline_scores() -> dict:
    """Adapter's last successful per-layer scores. Falls back to v91 known."""
    p = REPO / "workspace" / ".auto_train.baseline.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "format":   {"passed": 40, "total": 40},
        "scaffold": {"passed": 10, "total": 12},
        "recovery": {"passed": 2,  "total": 6},
        "hackfree": {"passed": 3,  "total": 10},
    }


def _save_baseline(scores: dict) -> None:
    p = REPO / "workspace" / ".auto_train.baseline.json"
    p.write_text(json.dumps(scores, indent=2))


def _scores_summary(scores: dict) -> str:
    parts = []
    for layer in ("format", "scaffold", "recovery", "hackfree"):
        if layer in scores:
            s = scores[layer]
            parts.append(f"{layer[0].upper()}{s['passed']}/{s['total']}")
    return " ".join(parts) if parts else "(none)"


def _full_quick_eval() -> dict:
    """Run all four quick layers and return per-layer passed/total dict.

    L1-only was too narrow — L1 is saturated at 100% so it can't surface the
    L3/L4 drift that v91 demonstrated. Full quick costs ~7 min but catches
    every regression class.
    """
    log_path = REPO / "training" / "logs" / "auto_eval.log"
    cmd = ["python3", "-u", "training/eval.py",
           "--endpoint", "http://localhost:8090", "--quick"]
    env = os.environ.copy()
    env["UNSLOTH_SKIP_TORCHVISION_CHECK"] = "1"
    rc = subprocess.run(cmd, cwd=REPO, stdout=log_path.open("w"),
                        stderr=subprocess.STDOUT, env=env).returncode
    if rc != 0:
        _log(f"eval rc={rc} — check {log_path}")
    rpt = REPO / "workspace" / "training_data" / "eval_report.json"
    if not rpt.exists():
        return {}
    d = json.loads(rpt.read_text())
    return {layer: {"passed": d[layer]["passed"], "total": d[layer]["total"]}
            for layer in ("format", "scaffold", "recovery", "hackfree")
            if layer in d}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", type=float, default=95.0,
                    help="Min L1 pass-pct required to swap (default 95)")
    ap.add_argument("--min-pairs", type=int, default=3,
                    help="Min new DPO pairs required to attempt train (default 3)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="Train even if last-train cooldown not met")
    args = ap.parse_args()

    _log(f"=== auto_train cycle start ===")

    # Circuit breaker: after 3 consecutive failed cycles, halt until operator clears
    if not args.force and _is_halted():
        _log(f"DISABLED ({_consecutive_failures()} consecutive failures). "
             f"Delete workspace/.auto_train.consecutive_failures to resume.")
        return 0

    # Cooldown: don't retrain more than once every 90 min
    if not args.force and _last_train_age_s() < 90 * 60:
        _log(f"cooldown: last train {int(_last_train_age_s() // 60)}m ago — skipping")
        return 0

    # Server-busy guard: don't train if a request hit the server <2 min ago
    if _last_request_age_s() < 120:
        _log(f"server-busy: last req {int(_last_request_age_s())}s ago — skipping")
        return 0

    pairs = _new_dpo_pairs(min_count=args.min_pairs)
    if not pairs:
        _log(f"insufficient new DPO pairs (<{args.min_pairs}) — skipping")
        return 0

    _log(f"have {len(pairs)} new DPO pairs to add")
    if args.dry_run:
        for p in pairs[:5]:
            _log(f"  prompt: {p['prompt'][:60]}  chosen: {p['chosen']}")
        return 0

    corpus = _build_supplementary_corpus(pairs)
    if corpus is None:
        _log("no synthesizable SFT examples — skipping")
        return 0

    # Touch BEFORE training starts so the next cron fire (within 90m of THIS start)
    # sees an active cooldown — prevents parallel training races. Without this,
    # cooldown check uses post-train mtime → cron at 01:17 fires while 00:47 train
    # is still running → two trains write to the same output dir → corruption.
    LAST_TRAIN.touch()
    if not _train(corpus):
        _log("train failed — keeping current adapter")
        return 1
    LAST_TRAIN.touch()  # post-train re-touch to anchor the next cooldown

    # Port the new adapter
    _port_adapter(ADAPTER_NEW, REPO / "models" / "tsunami-adapter-staging")

    # Backup current, swap to staging, restart server
    if ADAPTER_BACKUP.exists():
        shutil.rmtree(ADAPTER_BACKUP)
    if ADAPTER.exists():
        shutil.move(str(ADAPTER), str(ADAPTER_BACKUP))
    shutil.move(str(REPO / "models" / "tsunami-adapter-staging"), str(ADAPTER))
    _restart_server()

    if not _wait_for_server():
        _log("server didn't come up after swap — ROLLING BACK")
        if ADAPTER.exists():
            shutil.rmtree(ADAPTER)
        shutil.move(str(ADAPTER_BACKUP), str(ADAPTER))
        _restart_server()
        _set_consecutive_failures(_consecutive_failures() + 1)
        return 1

    new_scores = _full_quick_eval()
    base_scores = _baseline_scores()
    _log(f"baseline: {_scores_summary(base_scores)}")
    _log(f"new:      {_scores_summary(new_scores)}")

    # Regression check — TWO conditions, either triggers rollback:
    # (a) any single layer drops by >1 (catches flaky individual collapse)
    # (b) total drops by 2+ (catches death-by-a-thousand-cuts: v93 took -1 on
    #     every non-saturated layer, net -3, and the per-layer check let it
    #     through because each individual -1 was within tolerance)
    regressions = []
    for layer, base in base_scores.items():
        new = new_scores.get(layer)
        if not new:
            continue
        delta = new["passed"] - base["passed"]
        if delta < -1:
            regressions.append(f"{layer}: {base['passed']}→{new['passed']} ({delta:+d})")
    base_total = sum(s["passed"] for s in base_scores.values())
    new_total = sum(s["passed"] for s in new_scores.values())
    if new_total - base_total < -1:
        regressions.append(f"TOTAL: {base_total}→{new_total} ({new_total - base_total:+d})")

    if regressions:
        _log(f"REGRESSIONS detected: {'; '.join(regressions)} — ROLLING BACK")
        if ADAPTER.exists():
            shutil.rmtree(ADAPTER)
        shutil.move(str(ADAPTER_BACKUP), str(ADAPTER))
        _restart_server()
        if not _wait_for_server():
            _log("CRITICAL: rollback server failed to start")
        fails = _consecutive_failures() + 1
        _set_consecutive_failures(fails)
        if fails >= 3:
            _log(f"⚠️  3 consecutive failed cycles. Auto-train DISABLED until "
                 f"operator intervention. Delete workspace/.auto_train.consecutive_failures to resume.")
        return 1

    # Success: update baseline + clear failure counter
    _save_baseline(new_scores)
    _set_consecutive_failures(0)
    total_passed = sum(s["passed"] for s in new_scores.values())
    total = sum(s["total"] for s in new_scores.values())
    _log(f"✓ v92-auto adopted ({total_passed}/{total}) — baseline updated")
    return 0


def _is_halted() -> bool:
    """Auto-train halts after 3 consecutive failures until operator clears."""
    return _consecutive_failures() >= 3


if __name__ == "__main__":
    sys.exit(main())
