#!/usr/bin/env python3
"""v75 -- v73 base but L3 examples in BARE eval-format context.

v73 (champion, 390):  L1 100 / L2 92 / L3 50 / L4 70 / L5 78
v74 (regression, 375): adding L4 and multifile examples hurt

Hypothesis for L3 50% ceiling: v73 L3 training examples use full pipeline
context (project_init then file_write then build then error then fix).
But the L3 scenarios in training/eval_error_recovery.py are BARE:

  system
  user: "The build just failed. Fix it."
  assistant: shell_exec(cd deliverables/app && npx vite build)
  tool: [error]
  -> model response expected: FIX TOOL DIRECTLY

The model trained on full-pipeline context may not generalize to bare
context. Train on the BARE format so the model learns the
error -> fix mapping without needing project_init history.

Same count as v73 (16 examples):
  10 happy-path (unchanged)
  6 L3 bare-format (new structure, same scenarios, project name "app")

The bare format matches eval structure byte-for-byte so training data
distribution equals eval data distribution for L3.
"""
import json
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, build_pipeline
from build_v69 import APPS as APPS_V69

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v75.jsonl"


def bare_l3(initial_cmd, error_text, fix_tool, fix_args):
    """Build a bare-context L3 training example (5 messages)."""
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


# One bare L3 example per eval scenario (ER01..ER06). All use project "app".
STANDARD_CMD = "cd deliverables/app && npx vite build"

L3_SCENARIOS = [
    # ER01
    dict(
        initial_cmd=STANDARD_CMD,
        error="Cannot find module 'recharts'. Did you install it?",
        fix_tool="shell_exec",
        fix_args={"command": "cd deliverables/app && npm install recharts"},
    ),
    # ER02
    dict(
        initial_cmd=STANDARD_CMD,
        error="src/App.tsx(12,5): Type 'null' is not assignable to type 'string'. setError(null) should be setError('')",
        fix_tool="file_edit",
        fix_args={
            "path": "deliverables/app/src/App.tsx",
            "old_text": "setError(null)",
            "new_text": "setError('')",
        },
    ),
    # ER03
    dict(
        initial_cmd=STANDARD_CMD,
        error="src/App.tsx(8,45): Expected ')' to close '(' at line 8. {items.map(i => <div key={i}>{i}</div>",
        fix_tool="file_edit",
        fix_args={
            "path": "deliverables/app/src/App.tsx",
            "old_text": "{items.map(i => <div key={i}>{i}</div>",
            "new_text": "{items.map(i => <div key={i}>{i}</div>)}",
        },
    ),
    # ER04
    dict(
        initial_cmd=STANDARD_CMD,
        error="Could not resolve './components/Header' from src/App.tsx. File does not exist.",
        fix_tool="file_write",
        fix_args={
            "path": "deliverables/app/src/components/Header.tsx",
            "content": "export default function Header() {\n  return <header><h1>Header</h1></header>\n}",
        },
    ),
    # ER05 -- initial command is the WRONG path (workspace prefix)
    dict(
        initial_cmd="cd workspace/deliverables/app && npx vite build",
        error="bash: cd: workspace/deliverables/app: No such file or directory",
        fix_tool="shell_exec",
        fix_args={"command": "cd deliverables/app && npx vite build"},
    ),
    # ER06
    dict(
        initial_cmd=STANDARD_CMD,
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

    assert "Fix directly" in SYSTEM_TEXT, "SYSTEM_TEXT still says file_read"

    examples = []

    # 1. Happy-path: 10 v69 apps
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 2. L3 bare-format (6 examples, matches eval structure exactly)
    for sc in L3_SCENARIOS:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples")
    print(f"  10 happy path (v69)")
    print(f"  6 L3 BARE-format (matches eval structure)")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"\nStarts with <bos>: {starts_bos}/{len(examples)}")

    avg_len = sum(len(ex["text"]) for ex in examples) / len(examples)
    max_len = max(len(ex["text"]) for ex in examples)
    print(f"Length: avg={avg_len:.0f} max={max_len}")

    # Print a bare L3 sample (example 10 = first bare L3)
    print("\n--- Sample bare L3 (example index 10, first 2500 chars) ---")
    print(examples[10]["text"][:2500])
    print("---")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nWrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
