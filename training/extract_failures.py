#!/usr/bin/env python3
"""extract_failures.py — mine a session log for failure/correction pairs.

Reads a jsonl where each line has {type: user|assistant, message: {content}}
(Claude Code log format — also works on Tsunami session logs we'll produce
later once workspace/sessions/ is wired up).

Scans user↔assistant turn pairs looking for correction signals in the user's
NEXT turn — "no", "wrong", "that's not", "try again", "why did you" — and
emits a DPO-shaped pair:

    {
      "prompt":   <user message that preceded the failure>,
      "rejected": <assistant response that got corrected>,
      "chosen":   <assistant response the operator accepted>  (if present)
    }

Pairs without a `chosen` are still emitted (as `"chosen": null`) so you can
review them and write the correct response manually — the hardest part of
DPO data production is the chosen side, not the rejected.

Usage:
    python3 training/extract_failures.py <log.jsonl> [--out pairs.jsonl]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Phrases the operator uses when the last assistant turn was wrong.
# Match case-insensitively, at start of message (first 120 chars).
CORRECTION_PATTERNS = [
    r'^\s*no[,.\s]',
    r"^\s*that'?s not",
    r"^\s*that'?s wrong",
    r'^\s*wrong[,.\s]',
    r'^\s*why did (you|it)',
    r'^\s*(stop|don\'?t) ',
    r'^\s*try again',
    r'^\s*not (that|what)',
    r'^\s*fix (it|this|that)',
    r'^\s*nope[,.\s]',
    r'^\s*no\s*$',
    r'^\s*undo',
    r'^\s*revert',
    r'^\s*back out',
    r'^\s*that\'?s not (right|correct|what)',
    r'^\s*you (missed|forgot|skipped)',
]
CORR_RE = re.compile("|".join(CORRECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)


def _extract_text(msg) -> str:
    """Pull a plain-text representation from a message, regardless of whether
    `content` is a string or a list of {type, text}/{type, tool_use}/... blocks."""
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for block in c:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                name = block.get("name", "?")
                parts.append(f"[tool_use: {name}]")
            elif block.get("type") == "tool_result":
                r = block.get("content", "")
                if isinstance(r, list):
                    r = " ".join(b.get("text", "") for b in r if isinstance(b, dict))
                parts.append(f"[tool_result: {r[:120]}]")
        return "\n".join(parts).strip()
    return ""


def _iter_turns(log_path: Path):
    """Yield (role, text, line_index) for user/assistant messages in order.

    Skips system/progress/snapshot/queue-op lines. Handles Claude Code format
    (`type=user/assistant`, `message.content`) and falls back to the simpler
    `{role, content}` shape we'd use in tsunami session logs.
    """
    for i, raw in enumerate(log_path.open()):
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        # Claude Code
        if d.get("type") in ("user", "assistant"):
            msg = d.get("message", {})
            text = _extract_text(msg)
            if text.strip():
                yield (d["type"], text, i)
        # Simpler shape
        elif d.get("role") in ("user", "assistant"):
            text = _extract_text(d)
            if text.strip():
                yield (d["role"], text, i)


def extract_pairs(log_path: Path) -> list[dict]:
    """Walk turns, emit DPO pairs on correction signals."""
    turns = list(_iter_turns(log_path))
    pairs = []

    for i in range(len(turns) - 2):
        role, text, _ = turns[i]
        next_role, next_text, _ = turns[i + 1]
        # Pattern: user prompt, assistant response, user correction
        if role != "user" or next_role != "assistant":
            continue
        if i + 2 >= len(turns):
            continue
        third_role, third_text, _ = turns[i + 2]
        if third_role != "user":
            continue

        # Does the follow-up user turn look like a correction?
        if not CORR_RE.search(third_text[:150]):
            continue

        # Optional "chosen": the assistant turn AFTER the correction
        chosen = None
        if i + 3 < len(turns) and turns[i + 3][0] == "assistant":
            chosen = turns[i + 3][1]

        pairs.append({
            "prompt": text.strip()[:4000],
            "rejected": next_text.strip()[:4000],
            "chosen": chosen.strip()[:4000] if chosen else None,
            "correction_signal": third_text.strip()[:300],
            "turn_index": i,
        })

    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", help="Path to session jsonl")
    ap.add_argument("--out", default=None,
                    help="Output jsonl (default: <log_stem>.dpo_pairs.jsonl)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Max pairs to print to stdout as preview (0 = all)")
    args = ap.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out) if args.out else log_path.with_suffix(".dpo_pairs.jsonl")

    pairs = extract_pairs(log_path)
    with out_path.open("w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")

    with_chosen = sum(1 for p in pairs if p["chosen"])
    print(f"Scanned: {log_path}")
    print(f"Pairs extracted: {len(pairs)}")
    print(f"  With chosen (full pair): {with_chosen}")
    print(f"  Without chosen (needs operator completion): {len(pairs) - with_chosen}")
    print(f"Written: {out_path}")

    if args.limit or len(pairs) <= 5:
        for i, p in enumerate(pairs[: (args.limit or len(pairs))]):
            print(f"\n--- PAIR {i+1} (turn {p['turn_index']}) ---")
            print(f"PROMPT:      {p['prompt'][:200]}")
            print(f"REJECTED:    {p['rejected'][:200]}")
            print(f"CORRECTION:  {p['correction_signal'][:150]}")
            if p["chosen"]:
                print(f"CHOSEN:      {p['chosen'][:200]}")
            else:
                print("CHOSEN:      <none — operator to complete>")


if __name__ == "__main__":
    main()
