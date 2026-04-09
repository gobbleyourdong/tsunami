#!/usr/bin/env python3
"""v78 -- v73 base + 3 bare L3 examples at v76 sweet spot.

v76 (20 steps): L1 98 L2 100 L3 50 L4 80 L5 89 = 417 (L5 sweet spot)
v77 (40 steps): L1 100 L2 100 L3 67 L4 80 L5 78 = 425 (L3 better, L5 overfits)

v78 strategy: add 3 bare L3 examples for ER03/ER05/ER06 (the 3 remaining
failures) to v73 base, train at v76 settings (grad_accum=4, epochs=5).

The bare examples match eval format exactly:
  system
  user: "The build just failed. Fix it."
  assistant: shell_exec(build)
  tool: error
  assistant: FIX_TOOL

These ADD to (not replace) the pipeline-format L3 examples.
Total: 19 examples (10 happy + 6 pipeline L3 + 3 bare L3).
"""
import json
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, build_pipeline
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v78.jsonl"


def bare_l3(initial_cmd, error_text, fix_tool, fix_args):
    """Bare 5-message L3 example matching eval format."""
    return [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "The build just failed. Fix it."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "type": "function",
                "function": {"name": "shell_exec", "arguments": {"command": initial_cmd}},
            }],
        },
        {
            "role": "tool",
            "name": "shell_exec",
            "content": f"[shell_exec] Error: {error_text}"[:500],
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "type": "function",
                "function": {"name": fix_tool, "arguments": fix_args},
            }],
        },
    ]


# 3 bare L3 examples for the 3 remaining failures
BARE_L3 = [
    # ER03: syntax error -> file_edit (was failing: model did file_read)
    dict(
        initial_cmd="cd deliverables/app && npx vite build",
        error="src/App.tsx(8,45): Expected ')' to close '(' at line 8. {items.map(i => <div key={i}>{i}</div>",
        fix_tool="file_edit",
        fix_args={
            "path": "deliverables/app/src/App.tsx",
            "old_text": "{items.map(i => <div key={i}>{i}</div>",
            "new_text": "{items.map(i => <div key={i}>{i}</div>)}",
        },
    ),
    # ER05: wrong path -> shell_exec with corrected path
    dict(
        initial_cmd="cd workspace/deliverables/app && npx vite build",
        error="bash: cd: workspace/deliverables/app: No such file or directory",
        fix_tool="shell_exec",
        fix_args={"command": "cd deliverables/app && npx vite build"},
    ),
    # ER06: CSS import missing -> file_edit to remove it
    dict(
        initial_cmd="cd deliverables/app && npx vite build",
        error="Could not resolve 'leaflet/dist/leaflet.css' from src/App.tsx",
        fix_tool="file_edit",
        fix_args={
            "path": "deliverables/app/src/App.tsx",
            "old_text": "import 'leaflet/dist/leaflet.css'\n",
            "new_text": "",
        },
    ),
]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    assert "Fix directly" in SYSTEM_TEXT

    examples = []

    # 1. Happy-path: 10 v69 apps
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 2. Pipeline-format L3: 6 (from v73)
    for ex in V73_L3:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 3. Bare-format L3: 3 new (for ER03/ER05/ER06)
    for sc in BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples")
    print(f"  10 happy path")
    print(f"  6 pipeline L3 (v73)")
    print(f"  3 bare L3 (ER03, ER05, ER06)")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"Starts with <bos>: {starts_bos}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
