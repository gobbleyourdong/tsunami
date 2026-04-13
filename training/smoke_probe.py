#!/usr/bin/env python3
"""smoke_probe.py — progressive Tsunami smoke test, one prompt per call.

Reads cursor at workspace/tsu_smoke_cursor.txt (default 0), sends the Nth
prompt from PROBES to http://localhost:8090/v1/chat/completions, logs the
response to workspace/tsu_smoke_log.jsonl, advances cursor with wraparound.

Designed to be fired by a 10-minute cron so that over the course of a
training+iteration session we accumulate real evidence of how the model
handles ordinary user prompts — from the most basic ("hi") through CWD
operations to iteration. Each log line is pair-shaped so the same
extract_failures.py pipeline can convert these into DPO data once the
operator labels chosen/rejected.

Usage:
    python3 training/smoke_probe.py
    # prints a compact summary; full trace goes to the jsonl
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx


REPO = Path(__file__).resolve().parent.parent
CURSOR = REPO / "workspace" / "tsu_smoke_cursor.txt"
LOG = REPO / "workspace" / "tsu_smoke_log.jsonl"
ENDPOINT = os.environ.get("TSUNAMI_ENDPOINT", "http://localhost:8090")

# Progressive probe prompts — from trivial chat to iteration.
# Order matters: if the model fails at rung N, that's where work is needed.
PROBES = [
    # Chat tier — base model should answer naturally
    ("chat", "hi"),
    ("chat", "what's 2+2"),
    ("chat", "what can you build"),
    # CWD inspection — should shell_exec ls, not project_init
    ("cwd",  "what's in this directory"),
    ("cwd",  "list the files here"),
    ("cwd",  "summarize the python files"),
    ("cwd",  "find all TODO comments"),
    # CWD mutation — should shell_exec / file_edit, not project_init
    ("cwd",  "organize these files by type"),
    ("cwd",  "rename methodName to snake_case in user.py"),
    # Build tier — project_init is correct
    ("build", "build a counter"),
    ("build", "build a counter with plus and minus buttons"),
    # Iteration — file_edit, not project_init
    ("iter",  "add a reset button to the counter"),
]


def _read_cursor() -> int:
    if CURSOR.exists():
        try:
            return int(CURSOR.read_text().strip()) % len(PROBES)
        except ValueError:
            return 0
    return 0


def _write_cursor(n: int) -> None:
    CURSOR.parent.mkdir(parents=True, exist_ok=True)
    CURSOR.write_text(str(n % len(PROBES)))


def _append_log(record: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


def _classify(tier: str, name: str | None, content: str) -> str:
    """Heuristic pass/fail for the probe — quick-glance labeling only.

    `tier` is what the prompt targets; we compare to actually-called tool.
    """
    # Chat: any message_chat, message_result, or non-empty natural response
    if tier == "chat":
        if name in ("message_chat", "message_result") or (content and content.strip()):
            return "OK"
        return "FAIL(silent)"
    # CWD: should shell_exec or file_read / file_edit. project_init is wrong.
    if tier == "cwd":
        if name == "project_init":
            return "FAIL(scaffolded instead of inspecting)"
        if name in ("shell_exec", "file_read", "file_edit", "file_write", "message_result"):
            return "OK"
        return f"FAIL(tool={name})"
    # Build: should project_init.
    if tier == "build":
        if name == "project_init":
            return "OK"
        return f"FAIL(tool={name})"
    # Iter: file_edit (or file_read first). project_init fresh = wrong.
    if tier == "iter":
        if name == "project_init":
            return "FAIL(fresh scaffold instead of edit)"
        if name in ("file_edit", "file_read", "file_write"):
            return "OK"
        return f"FAIL(tool={name})"
    return "UNKNOWN"


def main():
    idx = _read_cursor()
    tier, prompt = PROBES[idx]

    # Single-turn chat completion, like the agent's first call.
    # We don't run the full agent loop — we just observe the model's first tool
    # choice, which is what matters for the progressive-failure diagnostic.
    tools_min = [{"type": "function", "function": {"name": n, "parameters": {"type": "object"}}}
                 for n in ("project_init", "file_write", "file_read", "file_edit",
                           "shell_exec", "search_web", "undertow", "riptide",
                           "generate_image", "message_result", "message_chat")]
    payload = {
        "model": "smoke",
        "messages": [{"role": "user", "content": prompt}],
        "tools": tools_min,
        "tool_choice": "auto",
        "temperature": 0.3,
        "max_tokens": 512,
    }

    t0 = time.time()
    error = None
    first_tool = None
    content = ""
    raw_status = None
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(f"{ENDPOINT}/v1/chat/completions", json=payload)
            raw_status = r.status_code
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            content = msg.get("content") or ""
            tcs = msg.get("tool_calls") or []
            if tcs:
                first_tool = tcs[0].get("function", {}).get("name")
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    elapsed = time.time() - t0
    verdict = _classify(tier, first_tool, content) if not error else f"ERROR({error[:80]})"

    record = {
        "ts": time.time(),
        "idx": idx,
        "tier": tier,
        "prompt": prompt,
        "http_status": raw_status,
        "first_tool": first_tool,
        "content_excerpt": content[:200],
        "elapsed_s": round(elapsed, 2),
        "verdict": verdict,
    }
    _append_log(record)
    _write_cursor(idx + 1)

    # Compact summary for cron output
    print(f"[{idx:02d}/{len(PROBES)}] [{tier}] {verdict} — {prompt!r}")
    print(f"      first_tool={first_tool!r} elapsed={elapsed:.1f}s")
    if content:
        print(f"      content: {content[:150]}")
    if error:
        print(f"      error:   {error[:200]}")


if __name__ == "__main__":
    main()
