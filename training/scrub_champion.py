#!/usr/bin/env python3
"""scrub_champion.py — strip dead-tool prose from champion dataset.

The champion jsonl was built using v69's SYSTEM_TEXT which talks about
swell, swell_analyze, swell_build, plan_update, message_info in its
"Ocean vocabulary" prose. Assistant-side tool calls are all clean (we
already filtered dead-tool-calling examples), but the teaching prose
still mentions tools the server rejects.

This script rewrites each example's system section to use a clean
SYSTEM_TEXT that mentions only the 11 live tools, while preserving the
conversation body unchanged.

Approach: regex replace the content between `<|turn>system\\n` and the
first `<turn|>\\n<|turn>user`, swapping in the new block rendered fresh.

Usage:
    python3 training/scrub_champion.py
    # reads:  workspace/training_data/e4b_toolcall_train_champion.jsonl
    # writes: workspace/training_data/e4b_toolcall_train_champion_clean.jsonl
"""
import json
import re
import os
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"

import argparse
_parser = argparse.ArgumentParser()
_parser.add_argument("--src", default="workspace/training_data/e4b_toolcall_train_champion.jsonl")
_parser.add_argument("--dst", default="workspace/training_data/e4b_toolcall_train_champion_clean.jsonl")
_args, _ = _parser.parse_known_args()
SRC = _args.src
DST = _args.dst


CLEAN_SYSTEM_TEXT = """You are Tsunami. You are the wave. You build apps by calling tools.

## The Ocean (your worldview)

- **wave**: you. A single forward execution. "Ride the wave. Land the wave."
- **tsunami**: the full agent. You are Tsunami.
- **ocean**: the system you operate in — context, tools, environment.
- **current**: your sense of direction per tool call. High tension = "I'm not sure." Low tension = "I'm confident." If uncertain, search first.
- **undertow**: QA. ALWAYS screenshot and verify HTML before delivering.
- **riptide**: vision grounding. Pull element positions from a reference image. Use on clone/mimic tasks.
- **break**: compile. shell_exec build after EVERY file_write. "Run the break."
- **reef**: error. Fix directly — type/syntax → file_edit; missing module → shell_exec npm install; missing file → file_write; wrong path → shell_exec with corrected path. CSS resolution errors → file_edit to remove or replace the import.
- **shore**: delivery. Land the wave at the shore.

## Before the Pipeline (pre-flight checks)

- Visual clones (user says "looks like X" or "style of Y" or "clone of Z") → search_web FIRST for reference images/layout, THEN project_init, THEN riptide on the reference.
- Conversational turn (greeting, question about capabilities) → message_chat(done=true).
- Default: go straight to project_init.

## The Pipeline (ride the wave in this order)

1. project_init(name) — scaffold
2. file_write(App.tsx) — write COMPLETE code (never a placeholder)
3. shell_exec build — run the break
4. IF reef (error): fix directly — file_edit (type/syntax fix), file_write (missing file), or shell_exec (install module, corrected path)
5. undertow(dist/index.html) — QA before delivery
6. message_result — land the wave at shore

## Components
Import from "./components/ui" (NOT "../components/ui/button" or other subpaths).
Available: Button, Card, Input, Badge, Dialog, Select, Progress, Avatar, Switch, Tooltip, Dropdown, Accordion, Alert, Skeleton.

## Rules
- NEVER skip the break.
- NEVER deliver without undertow.
- NEVER deliver a placeholder — file_write COMPLETE implementations on the first write.
- One tool call per response. Be brief.
- High pressure → search_web, don't guess.
"""


# The 11 live tools (no ghosts).
TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a project from the scaffold library.",
        "parameters": {"type": "OBJECT", "properties": {
            "name": {"description": "Project name", "type": "STRING"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "file_write",
        "description": "Create or overwrite a file with full content.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "content": {"type": "STRING"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "file_read",
        "description": "Read text content from a file.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "file_edit",
        "description": "Make targeted modifications to an existing file.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "old_text": {"type": "STRING"}, "new_text": {"type": "STRING"}},
            "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {
        "name": "shell_exec",
        "description": "Run a shell command and return its output.",
        "parameters": {"type": "OBJECT", "properties": {
            "command": {"type": "STRING"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Search the web for information.",
        "parameters": {"type": "OBJECT", "properties": {
            "query": {"type": "STRING"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "undertow",
        "description": "QA-test an HTML file in a headless browser. Auto-pulls levers (clicks, keys, text reads), takes screenshot, VLM-describes it.",
        "parameters": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "riptide",
        "description": "Extract element positions from a reference image. Returns ratio-based CSS positioning (percentages).",
        "parameters": {"type": "OBJECT", "properties": {
            "image_path": {"type": "STRING"}, "focus": {"type": "STRING"}},
            "required": ["image_path"]}}},
    {"type": "function", "function": {
        "name": "generate_image",
        "description": "Generate an image from a text description.",
        "parameters": {"type": "OBJECT", "properties": {
            "prompt": {"type": "STRING"}, "path": {"type": "STRING"}},
            "required": ["prompt", "path"]}}},
    {"type": "function", "function": {
        "name": "message_result",
        "description": "Deliver final outcome and end the task.",
        "parameters": {"type": "OBJECT", "properties": {
            "text": {"type": "STRING"}}}}},
    {"type": "function", "function": {
        "name": "message_chat",
        "description": "Talk to the user. done=true ends (no build happened).",
        "parameters": {"type": "OBJECT", "properties": {
            "text": {"type": "STRING"}, "done": {"type": "BOOLEAN"}}, "required": ["text"]}}},
]


def render_clean_system_prefix(tokenizer) -> str:
    """Render ONLY the system turn to use as a prefix. We extract the
    portion of the chat template that covers <bos><|turn>system...<turn|>
    by rendering a minimal conversation and trimming."""
    msgs = [{"role": "system", "content": CLEAN_SYSTEM_TEXT}, {"role": "user", "content": "__MARKER__"}]
    rendered = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    # Everything up to the "__MARKER__" in the user turn. But we want to
    # keep the <turn|>\n<|turn>user\n prefix and drop the marker.
    # Easier: find the position right before "__MARKER__" content starts,
    # then trim.
    idx = rendered.find("__MARKER__")
    if idx == -1:
        raise RuntimeError("could not locate marker in rendered template")
    # Walk back to the start of the user content (after <|turn>user\n)
    user_tag = "<|turn>user\n"
    user_start = rendered.rfind(user_tag, 0, idx)
    if user_start == -1:
        raise RuntimeError("could not locate user turn start")
    # Return everything up to and including the "<|turn>user\n" tag;
    # the body picks up from there.
    return rendered[:user_start + len(user_tag)]


def scrub_one(text: str, clean_prefix: str) -> str:
    """Replace the original system+user-prefix with the clean version."""
    # Find the original user-turn start
    user_tag = "<|turn>user\n"
    first_user = text.find(user_tag)
    if first_user == -1:
        raise RuntimeError("example has no <|turn>user — can't locate system boundary")
    # Keep everything after "<|turn>user\n" (the actual user content + rest of conversation)
    body = text[first_user + len(user_tag):]
    return clean_prefix + body


def main():
    print(f"Loading: {MODEL}")
    tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    clean_prefix = render_clean_system_prefix(tok)
    print(f"Clean prefix: {len(clean_prefix)} chars")

    # Sanity: verify no ghost tools in the prefix
    for ghost in ['match_glob', 'plan_update', 'swell_build', 'swell_analyze',
                  'message_info', 'message_ask', 'python_exec']:
        if ghost in clean_prefix:
            print(f"  WARNING: ghost '{ghost}' still in clean prefix")
    else:
        print("  prefix contains no dead-tool strings ✓")

    # Also filter out examples that CALL any dead tool (ghost assistant calls).
    DEAD_CALLS = ('plan_update', 'plan_advance', 'swell', 'swell_analyze',
                  'swell_build', 'match_glob', 'match_grep', 'message_info',
                  'message_ask', 'python_exec', 'summarize_file', 'file_append',
                  'browser_navigate')

    count_in, count_out, dropped = 0, 0, 0
    with open(SRC) as fsrc, open(DST, 'w') as fdst:
        for line in fsrc:
            count_in += 1
            d = json.loads(line)
            text = d['text']
            # Drop examples that call dead tools.
            calls = set(re.findall(r'call:([a-z_]+)', text))
            if any(c in DEAD_CALLS for c in calls):
                dropped += 1
                continue
            try:
                new_text = scrub_one(text, clean_prefix)
                fdst.write(json.dumps({'text': new_text}) + '\n')
                count_out += 1
            except Exception as e:
                print(f"  example {count_in}: scrub failed: {e}")

    print(f"\nDropped (dead-tool calls): {dropped}")

    print(f"\nRead:    {count_in}")
    print(f"Wrote:   {count_out}  → {DST}")

    # Audit final output
    print("\n=== DEAD-TOOL STRING AUDIT on clean output ===")
    with open(DST) as f:
        whole = f.read()
    for ghost in ['match_glob', 'match_grep', 'plan_update', 'plan_advance',
                  'swell_build', 'swell_analyze', 'swell', 'message_info',
                  'message_ask', 'python_exec', 'summarize_file',
                  'browser_navigate', 'file_append']:
        n = whole.count(ghost)
        mark = " ✓ CLEAN" if n == 0 else f" ✗ still {n} mentions"
        print(f"  {ghost}: {n}{mark}")

    # Tool-call distribution unchanged
    from collections import Counter
    c = Counter()
    with open(DST) as f:
        for line in f:
            for t in re.findall(r'call:([a-z_]+)', json.loads(line)['text']):
                c[t] += 1
    print("\n=== TOOL CALL DISTRIBUTION (should match pre-scrub) ===")
    for t, n in c.most_common():
        print(f"  {t}: {n}")


if __name__ == '__main__':
    main()
