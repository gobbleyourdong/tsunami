"""Light inference-server monitor.

Fires via cron. Each fire:
  1. Samples Qwen3.6 FP8 (:8095) process CPU/RSS + listening sockets
  2. Tails the llama-server log for recent POST /v1/chat/completions cadence
  3. Appends one row to ~/.tsunami/server_monitor.jsonl
  4. Rewrites ~/.tsunami/server_monitor.md with a rolling table

When the cron detects `idle_minutes >= 5` AND no queued B-leg is
currently running, drops a `~/.tsunami/opportunistic_runs/<ts>.pending`
marker so an operator (or a follow-up cron) can launch a B-leg without
contending with the active dev instance.

Never touches :8095 directly. Pure observation.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

_STATE_DIR = Path.home() / ".tsunami"
_JSONL = _STATE_DIR / "server_monitor.jsonl"
_MD = _STATE_DIR / "server_monitor.md"
_OPP_DIR = _STATE_DIR / "opportunistic_runs"

# Where llama-server writes stdout in the dev setup (verified in process
# list: python3 -u tsunami/serving/serve_qwen36_fp8.py). The log path
# comes from ComfyUI/logs or /tmp — cron picks the freshest match.
_LOG_GLOBS = ("/tmp/qwen36_fp8_back.log",
              "/tmp/qwen36_fp8_*.log",
              str(Path.home() / "ComfyUI" / "logs" / "qwen36*.log"))

_QWEN_PROCESS_RE = re.compile(r"serve_qwen36_fp8\.py")


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _ps_sample() -> dict:
    """Parse `ps aux | grep serve_qwen36_fp8` — returns CPU%, RSS_kb, pid."""
    try:
        out = subprocess.run(
            ["ps", "-e", "-o", "pid,pcpu,rss,command"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return {}
    for line in out.stdout.splitlines():
        if _QWEN_PROCESS_RE.search(line):
            parts = line.split(None, 3)
            if len(parts) >= 4:
                return {
                    "pid": int(parts[0]),
                    "cpu_pct": float(parts[1]),
                    "rss_kb": int(parts[2]),
                    "cmd": parts[3][:80],
                }
    return {}


def _gpu_utilization_pct() -> float | None:
    """nvidia-smi GPU utilization — the real decode-busy signal.

    Qwen FP8 process holds the model in KV cache at ~60% CPU whether or
    not it's decoding. GPU utilization spikes to >70% during active
    decode, drops to <15% when idle. Returns None if nvidia-smi is
    absent (e.g., Mac dev box).
    """
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    # First GPU only — Spark has one GB10.
    first = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
    try:
        return float(first.strip())
    except ValueError:
        return None


def _active_tsunami_subprocess() -> bool:
    """True if another `python -m tsunami` or tsunami worker is running
    against the shared server. Cheap proxy for 'operator is using this'."""
    try:
        out = subprocess.run(
            ["ps", "-e", "-o", "command"],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return False
    for line in out.stdout.splitlines():
        if ("python" in line and "-m tsunami" in line
                and "serving" not in line
                and "serve_" not in line):
            return True
    return False


def _recent_completion_lines(log_path: Path, since_epoch: float) -> list[str]:
    """Tail log_path; return lines mentioning /v1/chat/completions
    in the last since_epoch window. Approximate — uses wall time."""
    if not log_path.is_file():
        return []
    try:
        # Last 400 lines should be enough for a ~10-min window
        out = subprocess.run(
            ["tail", "-n", "400", str(log_path)],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return []
    hits = []
    for line in out.stdout.splitlines():
        if "/v1/chat/completions" in line:
            hits.append(line)
    return hits


def _find_log() -> Path | None:
    import glob
    candidates: list[Path] = []
    for pat in _LOG_GLOBS:
        for p in glob.glob(pat):
            candidates.append(Path(p))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _previous_sample() -> dict:
    if not _JSONL.is_file():
        return {}
    try:
        lines = _JSONL.read_text().strip().splitlines()
        if lines:
            return json.loads(lines[-1])
    except Exception:
        pass
    return {}


def _idle_minutes(log_path: Path | None) -> float | None:
    """Return minutes since the most recent chat completion.

    Uses log mtime as the activity proxy: uvicorn/llama-server writes
    a /v1/chat/completions log line per request, so mtime bumps on
    every request. No request in N min → mtime-now >= N min.
    Falls back to in-line timestamp parsing if some hits carry one.
    """
    if not log_path or not log_path.is_file():
        return None
    now = time.time()
    try:
        mtime = log_path.stat().st_mtime
        return max(0.0, (now - mtime) / 60.0)
    except Exception:
        return None


def collect() -> dict:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _find_log()
    sample = {
        "ts": _iso_now(),
        "qwen_process": _ps_sample(),
        "gpu_util_pct": _gpu_utilization_pct(),
        "tsunami_subprocess_active": _active_tsunami_subprocess(),
        "log_path": str(log_path) if log_path else "",
        "idle_minutes": _idle_minutes(log_path),
    }
    prev = _previous_sample()
    # Only flag restart if we have a prior sample AND the pid actually
    # changed. First-sample-ever is not a restart.
    prev_pid = prev.get("qwen_process", {}).get("pid")
    cur_pid = sample["qwen_process"].get("pid")
    if prev_pid and cur_pid and prev_pid != cur_pid:
        sample["restart_detected"] = True
    return sample


def write_jsonl(sample: dict) -> None:
    try:
        with _JSONL.open("a") as f:
            f.write(json.dumps(sample) + "\n")
    except Exception:
        pass


def write_markdown(last_n: int = 20) -> None:
    """Rewrite the rolling markdown report — last N samples."""
    if not _JSONL.is_file():
        return
    try:
        lines = _JSONL.read_text().strip().splitlines()[-last_n:]
    except Exception:
        return
    samples = [json.loads(l) for l in lines if l.strip()]
    if not samples:
        return
    rows = []
    for s in samples:
        p = s.get("qwen_process", {})
        cpu = f"{p.get('cpu_pct', 0):.0f}%" if p else "-"
        rss_gb = f"{p.get('rss_kb', 0) / (1024**2):.1f}G" if p else "-"
        idle = (f"{s['idle_minutes']:.1f}m"
                if s.get("idle_minutes") is not None else "-")
        restart = "🔁" if s.get("restart_detected") else ""
        rows.append(
            f"| {s['ts']} | {cpu:>5} | {rss_gb:>5} | {idle:>6} | {restart} |"
        )
    md = [
        "# Inference server monitor",
        "",
        f"Last updated: {_iso_now()}",
        f"Samples recorded: {len(samples)} (latest {last_n} below)",
        "",
        "| timestamp            |  CPU% |   RSS | idle  | event |",
        "|----------------------|------:|------:|------:|-------|",
        *rows,
        "",
        "## Interpretation",
        "",
        "- **CPU%** — Qwen3.6 FP8 decoder busy-ness. >50% = actively decoding.",
        "- **idle** — minutes since the last POST to /v1/chat/completions.",
        "  >5 min idle = opportunistic B-leg window.",
        "- **🔁 restart_detected** — pid changed since last sample.",
        "",
    ]
    try:
        _MD.write_text("\n".join(md))
    except Exception:
        pass


def maybe_queue_opportunistic(
    sample: dict,
    threshold_min: float = 5.0,
    max_gpu_pct: float = 40.0,
) -> bool:
    """Drop a .pending marker when server is idle across THREE signals:
       1. log mtime idle ≥ threshold_min
       2. GPU utilization < max_gpu_pct (model-loaded CPU baseline is
          ~60% but GPU drops to single-digits when no decode)
       3. no concurrent `python -m tsunami` subprocess is active

    The CPU metric is misleading because FP8 holds model weights in
    mem at a constant ~60% even when idle. GPU util is the real
    decode signal.
    """
    if sample.get("idle_minutes") is None:
        return False
    if sample["idle_minutes"] < threshold_min:
        return False
    gpu = sample.get("gpu_util_pct")
    if gpu is not None and gpu > max_gpu_pct:
        return False  # mid-decode
    if sample.get("tsunami_subprocess_active"):
        return False  # another instance is running
    _OPP_DIR.mkdir(parents=True, exist_ok=True)
    pending = list(_OPP_DIR.glob("*.pending"))
    if pending:
        return False  # already have one queued
    marker = _OPP_DIR / f"{_iso_now().replace(':','-')}.pending"
    try:
        marker.write_text(json.dumps({
            "reason": "server_idle",
            "idle_minutes": sample["idle_minutes"],
            "gpu_util_pct": sample.get("gpu_util_pct"),
            "cpu_pct": sample.get("qwen_process", {}).get("cpu_pct"),
            "sample": sample,
        }, indent=2))
        return True
    except Exception:
        return False


def main():
    sample = collect()
    write_jsonl(sample)
    write_markdown()
    queued = maybe_queue_opportunistic(sample)
    gpu = sample.get("gpu_util_pct")
    gpu_str = f"{gpu:.0f}%" if gpu is not None else "-"
    cpu = sample.get('qwen_process', {}).get('cpu_pct', '-')
    active = sample.get("tsunami_subprocess_active", False)
    idle = sample.get('idle_minutes', '-')
    idle_str = f"{idle:.1f}m" if isinstance(idle, (int, float)) else "-"
    print(f"[server_monitor] {sample['ts']}  "
          f"cpu={cpu}% gpu={gpu_str} idle={idle_str} "
          f"tsunami_active={active} queued={queued}")


if __name__ == "__main__":
    main()
