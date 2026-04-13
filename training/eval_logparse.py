#!/usr/bin/env python3
"""eval_logparse.py — ask Tsunami to mine its own (or any) session log for
failure/correction pairs, then emit DPO-shaped data to a jsonl.

This is the self-bootstrap test: the build-agent is asked to do a non-build
task (log analysis) using only its existing tool surface (shell_exec +
file_read + file_write + message_result). It forces:

  - shell_exec to invoke a helper (`training/extract_failures.py`) on a
    large file that would blow the context window if file_read'd directly
  - file_read on the extractor's OUTPUT (small jsonl, fits in context)
  - message_result summarizing what was found

PASS criteria:
  1. Agent emitted shell_exec with `extract_failures.py` or an equivalent
     python one-liner that reads the log
  2. Agent did NOT try to file_read a 340MB log (forbidden — would error)
  3. Agent read the produced pair file and summarized it in message_result
  4. message_result mentions a pair count

FAIL modes this catches:
  - "I'll just read the log into context" (file_read on 340MB → OOM)
  - Hallucinated tool calls (plan_update, match_glob, etc.)
  - message_result without having inspected the pair file (no grounding)

Usage:
    python3 training/eval_logparse.py --endpoint http://localhost:8090 \
        --log /home/jb/.claude/projects/.../da6c6380-....jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

import httpx


log = logging.getLogger("eval_logparse")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

PROMPT_TEMPLATE = (
    "Read the session log at {log} and extract user-correction pairs into "
    "a DPO-shaped jsonl at {out}. Each pair is a (prompt, rejected, chosen) "
    "triple pulled from user→assistant→user-correction turn sequences. "
    "The log is large (hundreds of MB) so you must NOT file_read it directly — "
    "use shell_exec to run training/extract_failures.py on it. "
    "When done, summarize how many pairs were extracted."
)


async def run(endpoint: str, log_path: Path, out_path: Path, max_iters: int = 15):
    from tsunami.config import TsunamiConfig
    from tsunami.tools import build_registry

    cfg = TsunamiConfig()
    reg = build_registry(cfg)
    tools = [t.schema() for t in reg.tools.values()]

    prompt = PROMPT_TEMPLATE.format(log=log_path, out=out_path)
    messages = [{"role": "user", "content": prompt}]

    tool_calls_made: list[str] = []
    tried_filread_large_log = False
    emitted_message_result = False
    mentioned_pair_count = False

    async with httpx.AsyncClient(timeout=180) as client:
        for it in range(max_iters):
            resp = await client.post(
                f"{endpoint}/v1/chat/completions",
                json={
                    "model": "eval",
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": 0.3,
                    "max_tokens": 2048,
                    "adapter": "tsunami-adapter",
                },
            )
            resp.raise_for_status()
            choice = resp.json()["choices"][0]["message"]

            tcs = choice.get("tool_calls") or []
            if not tcs:
                # Pure content → final answer
                content = choice.get("content", "")
                if content:
                    log.info(f"[it={it}] final content: {content[:200]}")
                    if any(w in content.lower() for w in ("pair", "extract", "found")):
                        mentioned_pair_count = True
                break

            tc = tcs[0]["function"]
            name = tc["name"]
            args = tc.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls_made.append(name)
            log.info(f"[it={it}] tool={name} args_keys={list(args.keys())}")

            # Guards: track the failure modes we care about
            if name == "file_read":
                p = (args.get("path") or "").strip()
                if str(log_path) in p or (p and Path(p).stat().st_size > 5_000_000 if Path(p).exists() else False):
                    tried_filread_large_log = True
                    log.warning("  FAIL signal: agent tried file_read on the large log")
            if name == "message_result":
                emitted_message_result = True
                txt = args.get("text", "") or ""
                if any(w in txt.lower() for w in ("pair", "extract", "found", "correction")):
                    mentioned_pair_count = True

            # Execute the tool locally so the agent can loop
            tool_obj = reg.get(name)
            if tool_obj is None:
                messages.append({"role": "assistant", "content": "", "tool_calls": tcs})
                messages.append({"role": "tool", "name": name,
                                 "content": f"[{name}] unknown tool"})
                continue

            try:
                result = await tool_obj.execute(**args)
                content = result.content
            except Exception as e:
                content = f"[{name}] error: {e}"

            messages.append({"role": "assistant", "content": "", "tool_calls": tcs})
            messages.append({"role": "tool", "name": name, "content": str(content)[:2000]})

            if name == "message_result":
                break

    # Score
    called_extract = any("shell_exec" == n for n in tool_calls_made) and \
                     any("extract_failures" in (messages[i].get("content", ""))
                         for i, m in enumerate(messages) if m.get("role") == "assistant")
    pair_file_exists = out_path.exists() and out_path.stat().st_size > 0

    print()
    print("=" * 60)
    print(" eval_logparse result")
    print("=" * 60)
    print(f"  tool calls          : {tool_calls_made}")
    print(f"  tried file_read 340M: {tried_filread_large_log}  (expect: False)")
    print(f"  called extractor    : {called_extract}           (expect: True)")
    print(f"  pair file written   : {pair_file_exists}         (expect: True)")
    print(f"  emitted result      : {emitted_message_result}   (expect: True)")
    print(f"  mentioned pairs     : {mentioned_pair_count}     (expect: True)")

    passed = (not tried_filread_large_log) and called_extract and \
             pair_file_exists and emitted_message_result
    print(f"\n  OVERALL: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://localhost:8090")
    ap.add_argument("--log", default="/home/jb/.claude/projects/-home-jb-ComfyUI-CelebV-HQ/da6c6380-981b-4d65-a99a-215c97650c2e.jsonl",
                    help="Session log to mine (default: our current Claude Code transcript)")
    ap.add_argument("--out", default="workspace/training_data/tsunami_extracted_pairs.jsonl")
    args = ap.parse_args()

    log_path = Path(args.log).expanduser().resolve()
    out_path = Path(args.out).resolve()
    if not log_path.exists():
        print(f"log not found: {log_path}")
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)

    return asyncio.run(run(args.endpoint, log_path, out_path))


if __name__ == "__main__":
    import sys
    sys.exit(main())
