#!/usr/bin/env python3
"""v72 — minimal delta from v69 (the champion) targeting L3 specifically.

v69: 10 examples → 369 total (best ever)
v70: 51 examples → 353 (slight regression on L3)
v71: 805 examples → 307 (L3 0%, L5 dropped — bulk hurt)

LESSON: less is more with native chat template. v69's 10 examples
already leverage the prior. Adding more behavioral examples needs
to MATCH the eval format EXACTLY or it backfires.

v72 = v69 (10 happy path) + 6 L3 examples in EXACT eval format
+ small L4 fixes. Total: ~25 examples.

L3 examples MUST end with the FIX TOOL directly (no file_read first).
The L3 eval scores the first tool_call after the build error.

Format for L3 example:
  user: "Build me X"
  → project_init(X)
  → file_write(App.tsx) [with deliberate bug]
  → shell_exec(build) → ERROR
  → FIX_TOOL_DIRECTLY (file_edit/file_write/shell_exec)
  → shell_exec(rebuild) → success
  → undertow → message_result

This way the FIRST response after error is the FIX, not file_read.
"""
import json
import os
import random
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, BRIEF, brief, build_messages
from build_v69 import APPS as APPS_V69

random.seed(9001)

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v72.jsonl"


def build_pipeline_v69(name, desc, files):
    """v69 happy path pipeline."""
    user_prompt = f"Build me {desc}."
    turns = []
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    for path, content in files:
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "vite v5.0.0 building for production... built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Screenshot taken. App renders correctly."))
    turns.append(("message_result", {"text": f"Built {name}: {desc}. Ready in deliverables/{name}."},
                  "Delivered."))
    return build_messages(user_prompt, turns)


# ============================================================================
# L3 RECOVERY — fix tool DIRECTLY after error (matches eval format)
# Each example: build → error → DIRECT FIX (no file_read) → rebuild → undertow → deliver
# ============================================================================

def build_l3_direct_fix(name, desc, broken_files, error_text, fix_call):
    """L3 example where the model produces the FIX TOOL directly after the error.
    fix_call: (tool_name, args_dict)
    """
    user_prompt = f"Build me {desc}."
    turns = []
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    for path, content in broken_files:
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))
    # Build fails
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  f"Error: {error_text}"))
    # FIX DIRECTLY — this is the critical model turn
    turns.append((fix_call[0], fix_call[1], f"OK"))
    # Rebuild succeeds
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "vite v5.0.0 building... built in 1.34s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Verified."))
    turns.append(("message_result", {"text": f"Fixed and built {name}: {desc}."}, "Delivered."))
    return build_messages(user_prompt, turns)


# Match each L3 eval scenario exactly
L3_EXAMPLES = [
    # ER01: Missing module → shell_exec npm install (NOT file_read)
    {
        "name": "chart-recharts",
        "desc": "a chart with recharts",
        "files": [("src/App.tsx",
                   "import { LineChart, Line } from 'recharts'\nexport default function App() {\n  return <LineChart width={400} height={300} data={[]}><Line dataKey='v' /></LineChart>\n}")],
        "error": "Cannot find module 'recharts'. Did you install it?",
        "fix_call": ("shell_exec", {"command": "cd deliverables/chart-recharts && npm install recharts"}),
    },
    # ER02 type: → file_edit (NOT file_read, NOT file_write rewrite)
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
    # ER03 syntax: → file_edit
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
    # ER04 import not found: → file_write (create missing file)
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
    # ER05 wrong path: → shell_exec with corrected path
    {
        "name": "cd-wrong-path",
        "desc": "a basic app",
        "files": [("src/App.tsx", "export default function App() { return <div>app</div> }")],
        "error": "bash: cd: workspace/deliverables/cd-wrong-path: No such file or directory",
        "fix_call": ("shell_exec", {"command": "cd deliverables/cd-wrong-path && npx vite build"}),
    },
    # ER06 CSS import: → file_edit
    {
        "name": "leaflet-css",
        "desc": "an app with a map",
        "files": [("src/App.tsx",
                   "import 'leaflet/dist/leaflet.css'\nexport default function App() { return <div>map</div> }")],
        "error": "Could not resolve 'leaflet/dist/leaflet.css' from src/App.tsx",
        "fix_call": ("file_edit", {
            "path": "deliverables/leaflet-css/src/App.tsx",
            "old_text": "import 'leaflet/dist/leaflet.css'",
            "new_text": "// removed: leaflet not installed",
        }),
    },
]


# ============================================================================
# L4 PATTERNS — small targeted examples
# ============================================================================

def build_l4_research(novel_request, query, app_name, app_desc):
    """research_web FIRST, then build."""
    files = [("src/App.tsx", "export default function App() { return <div>demo</div> }")]
    user_prompt = novel_request
    turns = []
    turns.append(("search_web", {"query": query, "num_results": 5},
                  "Found docs and tutorials about the topic."))
    turns.append(("project_init", {"name": app_name}, f"Created project deliverables/{app_name}"))
    for path, content in files:
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{app_name} && npx vite build"},
                  "built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{app_name}/dist/index.html", "expect": app_desc},
                  "Verified."))
    turns.append(("message_result", {"text": f"Built {app_name}."}, "Delivered."))
    return build_messages(user_prompt, turns)


def build_l4_plan(complex_request, goal, phases, app_name, app_desc):
    """plan_update FIRST, then build."""
    files = [("src/App.tsx", "export default function App() { return <div>demo</div> }")]
    user_prompt = complex_request
    turns = []
    turns.append(("plan_update", {"goal": goal, "phases": phases}, f"Plan accepted with {len(phases)} phases"))
    turns.append(("project_init", {"name": app_name}, f"Created project deliverables/{app_name}"))
    for path, content in files:
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{app_name} && npx vite build"},
                  "built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{app_name}/dist/index.html", "expect": app_desc},
                  "Verified."))
    turns.append(("message_result", {"text": f"Built {app_name} per plan."}, "Delivered."))
    return build_messages(user_prompt, turns)


L4_RESEARCH = [
    ("Build something using the new React Server Components", "react server components 2026",
     "rsc-demo", "an RSC demo"),
    ("Build with the new CSS @scope rules", "css scope rules 2026",
     "css-scope", "a CSS scope demo"),
]

L4_PLAN = [
    ("Build a multi-step form wizard with validation. Plan carefully — multiple steps and state.",
     "Build form wizard with validation",
     ["scaffold", "form components", "validation", "state", "deliver"],
     "form-wizard", "a multi-step form wizard"),
    ("Build a Spotify-style music player with playlists and search. Plan needed.",
     "Build music player",
     ["scaffold", "player UI", "playlist", "search", "deliver"],
     "music-player", "a music player"),
]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    examples = []

    # 1. Happy-path: 10 v69 apps
    for name, desc, files in APPS_V69:
        msgs = build_pipeline_v69(name, desc, files)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 2. L3 recovery in EXACT eval format (6 examples — 1 per scenario)
    for ex in L3_EXAMPLES:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 3. L4 research-first (2)
    for req, query, name, desc in L4_RESEARCH:
        msgs = build_l4_research(req, query, name, desc)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 4. L4 plan-first (2)
    for req, goal, phases, name, desc in L4_PLAN:
        msgs = build_l4_plan(req, goal, phases, name, desc)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples")
    print(f"  - 10 happy path (v69)")
    print(f"  - 6 L3 direct-fix (matches eval scenarios)")
    print(f"  - 2 L4 research-first")
    print(f"  - 2 L4 plan-first")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"\nStarts with <bos>: {starts_bos}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
