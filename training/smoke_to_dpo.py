#!/usr/bin/env python3
"""smoke_to_dpo.py — convert smoke-probe failures into DPO pair candidates.

Reads workspace/tsu_smoke_log.jsonl, finds entries not yet processed (cursor
at workspace/tsu_smoke_dpo.cursor), generates a {prompt, rejected, chosen}
row per FAIL, appends to workspace/tsu_smoke_dpo.jsonl.

`chosen` is a STRUCTURAL hint (correct tool + arg skeleton) derived from the
tier — operator fills the actual text/command/path in a later pass. For
mechanically obvious cases (chat-shaped FAILs where natural content already
exists) we can synthesize the chosen tool call directly.

Idempotent: re-running produces no duplicates because of the cursor.

Usage:
    python3 training/smoke_to_dpo.py
    # exits silently if no new failures since last run
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / "workspace" / "tsu_smoke_log.jsonl"
DPO = REPO / "workspace" / "tsu_smoke_dpo.jsonl"
CURSOR = REPO / "workspace" / "tsu_smoke_dpo.cursor"


def _read_cursor() -> int:
    if CURSOR.exists():
        try:
            return int(CURSOR.read_text().strip())
        except ValueError:
            return 0
    return 0


def _write_cursor(n: int) -> None:
    CURSOR.parent.mkdir(parents=True, exist_ok=True)
    CURSOR.write_text(str(n))


def _synthesize_chosen(tier: str, prompt: str, content: str) -> dict | None:
    """Generate a structural `chosen` from the failure tier + raw content.

    Returns a tool-call dict (operator may refine) or None if we can't infer.
    """
    p = prompt.lower()
    if tier == "chat":
        # If model produced natural content but as raw text (no tool call),
        # the right shape is message_chat(text=..., done=true).
        if content and content.strip():
            return {"tool": "message_chat",
                    "arguments": {"text": content.strip()[:500], "done": True}}
        return {"tool": "message_chat",
                "arguments": {"text": "<operator: write a short reply>", "done": True}}
    if tier == "cwd":
        # Inspect prompts → ls. Organize → ls + mkdir+mv. Find/grep → grep -rn.
        if "todo" in p or "find" in p:
            return {"tool": "shell_exec",
                    "arguments": {"command": "grep -rn 'TODO' --include='*.py' --include='*.ts' --include='*.tsx'"}}
        if "organize" in p or "by type" in p:
            return {"tool": "shell_exec",
                    "arguments": {"command": "ls -la"}}  # then operator chains mkdir+mv
        if "rename" in p:
            return {"tool": "file_read",
                    "arguments": {"path": "<operator: target file from prompt>"}}
        if "summarize" in p:
            return {"tool": "shell_exec",
                    "arguments": {"command": "ls *.py && wc -l *.py"}}
        # Default CWD inspection
        return {"tool": "shell_exec",
                "arguments": {"command": "ls -la"}}
    if tier == "build":
        # Derive a reasonable project name slug from the prompt
        slug = "-".join(w for w in p.replace("build", "").replace("create", "")
                        .replace("a ", "").split()[:3] if w).strip("-") or "app"
        return {"tool": "project_init", "arguments": {"name": slug}}
    if tier == "iter":
        return {"tool": "file_edit",
                "arguments": {"path": "<operator: existing project file>",
                              "old_text": "<operator: snippet to replace>",
                              "new_text": "<operator: replacement>"}}
    return None


def main():
    if not LOG.exists():
        print("no smoke log yet")
        return

    cursor = _read_cursor()
    lines = LOG.read_text().splitlines()
    new_lines = lines[cursor:]
    if not new_lines:
        print(f"cursor at {cursor}, no new probes")
        return

    appended = 0
    DPO.parent.mkdir(parents=True, exist_ok=True)
    with DPO.open("a") as out:
        for line in new_lines:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            verdict = d.get("verdict", "")
            if not verdict.startswith("FAIL") and not verdict.startswith("ERROR"):
                continue
            chosen = _synthesize_chosen(d["tier"], d["prompt"], d.get("content_excerpt", ""))
            pair = {
                "ts": d["ts"],
                "tier": d["tier"],
                "prompt": d["prompt"],
                "rejected": {
                    "first_tool": d.get("first_tool"),
                    "content": d.get("content_excerpt", ""),
                },
                "chosen": chosen,
                "verdict": verdict,
                "needs_operator_review": (chosen is None
                                          or any("<operator" in str(v) for v in (chosen or {}).get("arguments", {}).values())),
            }
            out.write(json.dumps(pair) + "\n")
            appended += 1

    _write_cursor(len(lines))
    total = sum(1 for _ in DPO.open()) if DPO.exists() else 0
    print(f"smoke_to_dpo: scanned {len(new_lines)} new probes, "
          f"appended {appended} DPO pairs, total {total} in {DPO.name}")


if __name__ == "__main__":
    main()
