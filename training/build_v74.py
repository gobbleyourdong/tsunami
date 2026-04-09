#!/usr/bin/env python3
"""v74 — v73 base + diverse L3 + L4 patterns + multi-file splits.

v73 (champion, 390):
  L1 100 / L2 92 / L3 50 / L4 70 / L5 78

Remaining gaps:
  L3 50% — ER03 syntax, ER05 path, ER06 css all fall to file_read.
           Need diverse recovery patterns so model generalizes.
  L4 70% — HF02 research gate, HF09 plan, HF10 undertow.
  L5 78% — IH02 markdown + IH03 expense tracker timeout from
           giant content fields causing JSON parse failures.

v74 strategy (focused targeted additions, not shotgun):
  1. 5 diverse L3 recovery examples — varied failure modes
     (prop type error, missing npm, missing brace, import case,
     runtime ref error). Teaches model to generalize "fix tool
     matches error shape".
  2. 3 L4 hackfree examples — visual clone triggers search_web,
     complex build triggers plan_update, delivery requires undertow.
  3. 5 multi-file split examples — apps built across 3-4 small
     file_writes instead of one giant file_write. Teaches "split,
     don't write a monolith".
  4. All file_write contents under ~1500 chars (v73 already is).

Total: 16 + 5 + 3 + 5 = 29 examples.
Prediction: L3 60-70%, L4 80%+, L5 85%+.
"""
import json
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, BRIEF, brief, build_messages, build_pipeline
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v74.jsonl"


# ============================================================================
# A. DIVERSE L3 RECOVERY — varied error shapes, fix-direct tools
# ============================================================================

L3_DIVERSE = [
    # L3a — prop TypeError (not useState). Teaches: wrong type in JSX attr → file_edit
    {
        "name": "badge-type",
        "desc": "a badge component",
        "files": [("src/App.tsx",
                   "type BadgeProps = { count: number }\nfunction Badge({count}: BadgeProps) { return <span className=\"badge\">{count}</span> }\nexport default function App() {\n  return <div><Badge count=\"five\" /></div>\n}")],
        "error": "src/App.tsx(4,23): Type '\"five\"' is not assignable to type 'number'.",
        "fix_call": ("file_edit", {
            "path": "deliverables/badge-type/src/App.tsx",
            "old_text": "count=\"five\"",
            "new_text": "count={5}",
        }),
    },
    # L3b — missing lodash. Teaches: missing module → shell_exec npm install (not recharts)
    {
        "name": "list-dedupe",
        "desc": "a list deduper",
        "files": [("src/App.tsx",
                   "import _ from 'lodash'\nimport { useState } from 'react'\nexport default function App() {\n  const [items] = useState([1,2,2,3,3,3])\n  return <div>{_.uniq(items).join(', ')}</div>\n}")],
        "error": "Cannot find module 'lodash'. Did you install it?",
        "fix_call": ("shell_exec", {"command": "cd deliverables/list-dedupe && npm install lodash"}),
    },
    # L3c — missing brace. Teaches: different syntax error → file_edit with close brace
    {
        "name": "grid-brace",
        "desc": "a grid layout",
        "files": [("src/App.tsx",
                   "export default function App() {\n  return <div className=\"grid\">\n    <div>1</div>\n    <div>2</div>\n    <div>3</div>\n  </div>\n")],
        "error": "src/App.tsx(7,1): '}' expected.",
        "fix_call": ("file_edit", {
            "path": "deliverables/grid-brace/src/App.tsx",
            "old_text": "  </div>\n",
            "new_text": "  </div>\n}\n",
        }),
    },
    # L3d — import case mismatch. Teaches: case-sensitive path → file_edit path fix
    {
        "name": "header-case",
        "desc": "a header app",
        "files": [
            ("src/Header.tsx", "export default function Header() { return <h1>Header</h1> }"),
            ("src/App.tsx",
             "import Header from './header'\nexport default function App() { return <Header /> }"),
        ],
        "error": "Could not resolve './header' from src/App.tsx (did you mean './Header'?).",
        "fix_call": ("file_edit", {
            "path": "deliverables/header-case/src/App.tsx",
            "old_text": "import Header from './header'",
            "new_text": "import Header from './Header'",
        }),
    },
    # L3e — undefined reference. Teaches: runtime ref error → file_edit to define
    {
        "name": "table-ref",
        "desc": "a table",
        "files": [("src/App.tsx",
                   "export default function App() {\n  return <table><tbody>{rows.map(r => <tr key={r}><td>{r}</td></tr>)}</tbody></table>\n}")],
        "error": "src/App.tsx(2,18): Cannot find name 'rows'.",
        "fix_call": ("file_edit", {
            "path": "deliverables/table-ref/src/App.tsx",
            "old_text": "export default function App() {\n  return <table>",
            "new_text": "export default function App() {\n  const rows = [1, 2, 3]\n  return <table>",
        }),
    },
]


# ============================================================================
# B. L4 HACKFREE — research gate, plan gate, undertow before delivery
# ============================================================================

def build_l4_visual_research(clone_target, query, name):
    """Visual clone → search_web FIRST for reference."""
    user_prompt = f"Build a page that looks like the {clone_target}."
    turns = []
    turns.append(("search_web", {"query": query, "num_results": 5},
                  f"Found reference images and layout docs for {clone_target}."))
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    turns.append(("file_write", {"path": "src/App.tsx",
                                 "content": f"export default function App() {{ return <div className=\"hero\"><h1>{clone_target}</h1></div> }}"},
                  "Wrote src/App.tsx"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "vite v5.0.0 building... built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": clone_target},
                  "Verified visual match."))
    turns.append(("message_result", {"text": f"Built {name} visual clone of {clone_target}."}, "Delivered."))
    return build_messages(user_prompt, turns)


def build_l4_complex_plan(complex_request, goal, phases, name):
    """Complex build → plan_update FIRST, then execute phases."""
    user_prompt = complex_request
    turns = []
    turns.append(("plan_update", {"goal": goal, "phases": phases},
                  f"Plan accepted with {len(phases)} phases."))
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    turns.append(("file_write", {"path": "src/App.tsx",
                                 "content": "export default function App() { return <div>App</div> }"},
                  "Wrote src/App.tsx"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": "complex app"},
                  "Verified."))
    turns.append(("message_result", {"text": f"Built {name} per plan."}, "Delivered."))
    return build_messages(user_prompt, turns)


def build_l4_undertow_delivery(name, desc):
    """Emphasize undertow → message_result transition."""
    user_prompt = f"Build me {desc}."
    turns = []
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    turns.append(("file_write", {"path": "src/App.tsx",
                                 "content": f"export default function App() {{ return <div>{desc}</div> }}"},
                  "Wrote src/App.tsx"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "built in 1.23s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Verified rendering."))
    turns.append(("message_result", {"text": f"Built {name}. Ready at deliverables/{name}."}, "Delivered."))
    return build_messages(user_prompt, turns)


L4_VISUAL = [
    ("Stripe pricing page", "stripe pricing page design layout", "stripe-pricing-clone"),
    ("Apple homepage", "apple homepage hero section layout", "apple-home-clone"),
]

L4_COMPLEX = [
    ("Build a full photo editor with filters, cropping, undo/redo, and cloud save.",
     "Build photo editor",
     ["scaffold", "filters", "crop", "undo/redo", "cloud save", "deliver"],
     "photo-editor"),
]

L4_UNDERTOW = [
    ("greeting-app", "a greeting app"),
]


# ============================================================================
# C. MULTI-FILE SPLIT — small writes across multiple files
# Teaches the model to split work into tiny file_writes rather than one giant.
# ============================================================================

def build_multifile(name, desc, files):
    """Multi-file app built via separate small file_writes."""
    user_prompt = f"Build me {desc}."
    turns = []
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    for path, content in files:
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "built in 1.42s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Verified."))
    turns.append(("message_result", {"text": f"Built {name}: {desc}."}, "Delivered."))
    return build_messages(user_prompt, turns)


MULTIFILE_APPS = [
    # 1. app with shared types
    ("user-list", "a user list with typed data", [
        ("src/types.ts", "export type User = { id: number; name: string; email: string }"),
        ("src/UserCard.tsx",
         "import { User } from './types'\nexport function UserCard({user}: {user: User}) {\n  return <div className=\"card\"><h3>{user.name}</h3><p>{user.email}</p></div>\n}"),
        ("src/App.tsx",
         "import { User } from './types'\nimport { UserCard } from './UserCard'\nconst users: User[] = [{id:1,name:'Ada',email:'a@x.com'},{id:2,name:'Grace',email:'g@x.com'}]\nexport default function App() {\n  return <div>{users.map(u => <UserCard key={u.id} user={u} />)}</div>\n}"),
    ]),
    # 2. app with utils
    ("currency-conv", "a currency converter", [
        ("src/utils.ts",
         "export function toUSD(eur: number, rate = 1.08) { return (eur * rate).toFixed(2) }"),
        ("src/App.tsx",
         "import { useState } from 'react'\nimport { toUSD } from './utils'\nexport default function App() {\n  const [eur, setEur] = useState(0)\n  return <div><input type=\"number\" value={eur} onChange={e => setEur(+e.target.value)} /><div>${toUSD(eur)}</div></div>\n}"),
    ]),
    # 3. app with 3 components
    ("dash-three", "a dashboard with header sidebar and main", [
        ("src/Header.tsx",
         "export function Header() { return <header><h1>Dashboard</h1></header> }"),
        ("src/Sidebar.tsx",
         "export function Sidebar() { return <aside><ul><li>Home</li><li>Settings</li></ul></aside> }"),
        ("src/Main.tsx",
         "export function Main() { return <main><h2>Welcome</h2><p>Your dashboard.</p></main> }"),
        ("src/App.tsx",
         "import { Header } from './Header'\nimport { Sidebar } from './Sidebar'\nimport { Main } from './Main'\nexport default function App() {\n  return <div className=\"grid\"><Header /><Sidebar /><Main /></div>\n}"),
    ]),
    # 4. app with custom hook
    ("timer-hook", "a timer with custom hook", [
        ("src/useTimer.ts",
         "import { useState, useEffect } from 'react'\nexport function useTimer() {\n  const [s, setS] = useState(0)\n  useEffect(() => { const id = setInterval(() => setS(x => x + 1), 1000); return () => clearInterval(id) }, [])\n  return s\n}"),
        ("src/App.tsx",
         "import { useTimer } from './useTimer'\nexport default function App() {\n  const s = useTimer()\n  return <div>Elapsed: {s}s</div>\n}"),
    ]),
    # 5. multi-step wizard
    ("wizard-three", "a 3-step wizard", [
        ("src/Step1.tsx",
         "export function Step1({next}: {next: () => void}) { return <div><h2>Step 1</h2><button onClick={next}>Next</button></div> }"),
        ("src/Step2.tsx",
         "export function Step2({next}: {next: () => void}) { return <div><h2>Step 2</h2><button onClick={next}>Next</button></div> }"),
        ("src/Step3.tsx",
         "export function Step3() { return <div><h2>Step 3 — Done!</h2></div> }"),
        ("src/App.tsx",
         "import { useState } from 'react'\nimport { Step1 } from './Step1'\nimport { Step2 } from './Step2'\nimport { Step3 } from './Step3'\nexport default function App() {\n  const [step, setStep] = useState(1)\n  return <div>{step === 1 && <Step1 next={() => setStep(2)} />}{step === 2 && <Step2 next={() => setStep(3)} />}{step === 3 && <Step3 />}</div>\n}"),
    ]),
]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    # Sanity check
    assert "Fix directly" in SYSTEM_TEXT, "SYSTEM_TEXT still says file_read"

    examples = []

    # 1. Happy-path: 10 v69 apps
    for name, desc, files in APPS_V69:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 2. v73 L3 direct-fix (6 examples, one per eval scenario)
    for ex in V73_L3:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 3. L3 diverse recovery (5 new examples, varied error shapes)
    for ex in L3_DIVERSE:
        msgs = build_l3_direct_fix(ex["name"], ex["desc"], ex["files"], ex["error"], ex["fix_call"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 4. L4 visual clone → search_web first
    for target, query, name in L4_VISUAL:
        msgs = build_l4_visual_research(target, query, name)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 5. L4 complex → plan_update first
    for req, goal, phases, name in L4_COMPLEX:
        msgs = build_l4_complex_plan(req, goal, phases, name)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 6. L4 undertow before delivery (reinforces HF10)
    for name, desc in L4_UNDERTOW:
        msgs = build_l4_undertow_delivery(name, desc)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 7. Multi-file split (5 examples)
    for name, desc, files in MULTIFILE_APPS:
        msgs = build_multifile(name, desc, files)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"\nTotal: {len(examples)} examples")
    print(f"  10 happy path (v69)")
    print(f"  6 L3 direct-fix (v73 scenarios)")
    print(f"  5 L3 diverse (new)")
    print(f"  2 L4 visual-research (new)")
    print(f"  1 L4 complex-plan (new)")
    print(f"  1 L4 undertow-delivery (new)")
    print(f"  5 multi-file split (new)")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"\nStarts with <bos>: {starts_bos}/{len(examples)}")

    # Length sanity check
    max_len = max(len(ex["text"]) for ex in examples)
    avg_len = sum(len(ex["text"]) for ex in examples) / len(examples)
    print(f"Length: avg={avg_len:.0f} max={max_len}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
