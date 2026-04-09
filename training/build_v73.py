#!/usr/bin/env python3
"""v73 — unify prompt + keep v72 L3 wins + revert L4 additions.

v69:  10 happy only     = 369 (L1 98 / L2 100 / L3 33 / L4 60 / L5 78)
v72f: 10 happy + 6 L3 + 4 L4 = 357 (L1 98 / L2 92 / L3 50 / L4 50 / L5 67)

ANALYSIS: v72 L3 +17 but L2 -8, L4 -10, L5 -11.
- shell_loops jumped 6 -> 43: model oscillates between file_read (prompt)
  and fix-direct (examples). PROMPT CONTRADICTION.
- L4 regressed: L4 research/plan examples overfit.
- L2 regressed: stochastic.

FIX: v73 = v69 prompt REWRITTEN to fix-direct + 6 L3 direct-fix examples.
NO L4 training examples. Let Gemma's prior handle L4 via the fixed prompt.

Total: 16 examples (10 happy + 6 L3). Prompt now CONSISTENT with all evals.

Critical: build_v69 SYSTEM_TEXT was updated in-place to the fix-direct
wording. This file imports from it, so the 10 happy-path examples get
the new prompt automatically.

Predicted: L3 50%+ (retained), L4 60%+ (recovered via prompt consistency),
L2 100% (recovered), L5 78%+ (no more shell-loop oscillation).
"""
import json
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, BRIEF, brief, build_messages, build_pipeline
from build_v69 import APPS as APPS_V69

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v73.jsonl"


def build_l3_direct_fix(name, desc, broken_files, error_text, fix_call):
    """Full pipeline with direct fix after error (no file_read)."""
    user_prompt = f"Build me {desc}."
    turns = []
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    for path, content in broken_files:
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  f"Error: {error_text}"))
    turns.append((fix_call[0], fix_call[1], "OK"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "vite v5.0.0 building... built in 1.34s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Verified."))
    turns.append(("message_result", {"text": f"Fixed and built {name}: {desc}."}, "Delivered."))
    return build_messages(user_prompt, turns)


# One example per L3 eval scenario — matches the exact tool expected
L3_EXAMPLES = [
    # ER01: Missing module → shell_exec npm install
    {
        "name": "chart-recharts",
        "desc": "a chart with recharts",
        "files": [("src/App.tsx",
                   "import { LineChart, Line } from 'recharts'\nexport default function App() {\n  return <LineChart width={400} height={300} data={[]}><Line dataKey='v' /></LineChart>\n}")],
        "error": "Cannot find module 'recharts'. Did you install it?",
        "fix_call": ("shell_exec", {"command": "cd deliverables/chart-recharts && npm install recharts"}),
    },
    # ER02: Type error → file_edit
    {
        "name": "counter-type",
        "desc": "a counter app",
        "files": [("src/App.tsx",
                   "import { useState } from 'react'\nexport default function App() {\n  const [count, setCount] = useState<string>(0)\n  return <button onClick={() => setCount(count + 1)}>{count}</button>\n}")],
        "error": "src/App.tsx(3,33): Type '0' is not assignable to type 'string'.",
        "fix_call": ("file_edit", {
            "path": "deliverables/counter-type/src/App.tsx",
            "old_text": "useState<string>(0)",
            "new_text": "useState<number>(0)",
        }),
    },
    # ER03: Syntax error → file_edit
    {
        "name": "list-syntax",
        "desc": "a list",
        "files": [("src/App.tsx",
                   "export default function App() {\n  const items = [1, 2, 3]\n  return <ul>{items.map(i => <li>{i}</li>}</ul>\n}")],
        "error": "src/App.tsx(3,42): ')' expected.",
        "fix_call": ("file_edit", {
            "path": "deliverables/list-syntax/src/App.tsx",
            "old_text": "items.map(i => <li>{i}</li>}",
            "new_text": "items.map(i => <li>{i}</li>)}",
        }),
    },
    # ER04: Import not found → file_write (create missing file)
    {
        "name": "header-missing",
        "desc": "an app with a header",
        "files": [("src/App.tsx",
                   "import Header from './Header'\nexport default function App() {\n  return <div><Header /><h1>App</h1></div>\n}")],
        "error": "Could not resolve './Header' from src/App.tsx. File does not exist.",
        "fix_call": ("file_write", {
            "path": "deliverables/header-missing/src/Header.tsx",
            "content": "export default function Header() {\n  return <header><h1>Header</h1></header>\n}",
        }),
    },
    # ER05: Wrong path → shell_exec with corrected path
    {
        "name": "cd-wrong-path",
        "desc": "a basic app",
        "files": [("src/App.tsx", "export default function App() { return <div>app</div> }")],
        "error": "bash: cd: workspace/deliverables/cd-wrong-path: No such file or directory",
        "fix_call": ("shell_exec", {"command": "cd deliverables/cd-wrong-path && npx vite build"}),
    },
    # ER06: CSS import missing → file_edit (remove the bad import)
    {
        "name": "leaflet-css",
        "desc": "an app with a map",
        "files": [("src/App.tsx",
                   "import 'leaflet/dist/leaflet.css'\nexport default function App() { return <div>map</div> }")],
        "error": "Could not resolve 'leaflet/dist/leaflet.css' from src/App.tsx",
        "fix_call": ("file_edit", {
            "path": "deliverables/leaflet-css/src/App.tsx",
            "old_text": "import 'leaflet/dist/leaflet.css'\n",
            "new_text": "",
        }),
    },
]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    # Sanity check: v69 SYSTEM_TEXT must say fix-direct, not file_read
    assert "Fix directly" in SYSTEM_TEXT, "build_v69.SYSTEM_TEXT still says file_read — update it first"
    assert "fix directly" in SYSTEM_TEXT, "build_v69.SYSTEM_TEXT pipeline still says file_read — update it first"
    print("SYSTEM_TEXT reef/pipeline uses fix-direct wording.")

    examples = []

    # 1. Happy-path: 10 v69 apps (with updated fix-direct SYSTEM_TEXT)
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 2. L3 direct-fix: 6 examples (1 per eval scenario)
    for ex in L3_EXAMPLES:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples")
    print(f"  - 10 happy path (v69, updated prompt)")
    print(f"  - 6 L3 direct-fix (one per eval scenario)")
    print(f"  - 0 L4 examples (v72 L4 additions backfired)")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"\nStarts with <bos>: {starts_bos}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
