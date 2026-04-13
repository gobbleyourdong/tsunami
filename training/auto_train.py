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


def _quick_eval_l1() -> tuple[int, int]:
    """Run eval.py L1-only and return (passed, total)."""
    log_path = REPO / "training" / "logs" / "auto_eval.log"
    cmd = ["python3", "-u", "training/eval.py",
           "--endpoint", "http://localhost:8090", "--quick", "--layers", "format"]
    env = os.environ.copy()
    env["UNSLOTH_SKIP_TORCHVISION_CHECK"] = "1"
    rc = subprocess.run(cmd, cwd=REPO, stdout=log_path.open("w"),
                        stderr=subprocess.STDOUT, env=env).returncode
    if rc != 0:
        _log(f"eval rc={rc} — check {log_path}")
    # Parse the report
    rpt = REPO / "workspace" / "training_data" / "eval_report.json"
    if not rpt.exists():
        return (0, 1)
    d = json.loads(rpt.read_text())
    f = d.get("format", {})
    return (f.get("passed", 0), f.get("total", 1))


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

    if not _train(corpus):
        _log("train failed — keeping current adapter")
        return 1
    LAST_TRAIN.touch()

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
        return 1

    passed, total = _quick_eval_l1()
    pct = 100.0 * passed / max(total, 1)
    _log(f"L1 quick-eval: {passed}/{total} ({pct:.0f}%) — floor={args.floor}")

    if pct < args.floor:
        _log(f"REGRESSED below floor — ROLLING BACK to previous adapter")
        if ADAPTER.exists():
            shutil.rmtree(ADAPTER)
        shutil.move(str(ADAPTER_BACKUP), str(ADAPTER))
        _restart_server()
        if not _wait_for_server():
            _log("CRITICAL: rollback server failed to start")
        return 1

    _log(f"v92-auto adopted ({pct:.0f}% L1) — server now serving new adapter")
    return 0


if __name__ == "__main__":
    sys.exit(main())
