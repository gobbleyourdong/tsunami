#!/usr/bin/env python3
"""v70 = v69's native chat template approach + expanded example pool.

v69 fixed the format bottleneck (10 examples → L5 78%, +56 over v18).
v70 expands example diversity to also recover L3/L4 to v14r levels.

Total target: ~60 examples
- 25 simple single-file apps (diverse domains)
- 8 medium multi-file apps
- 5 multi-tool-call examples (single response, multiple calls)
- 6 L3 multi-turn error recovery (NEW format with <|turn>tool)
- 4 L4 research-first (HF02)
- 3 L4 plan-first (HF09)
- 4 L4 dedup-guard (HF08)

All use tokenizer.apply_chat_template() — same format as v69.
"""
import json
import os
import random

from transformers import AutoTokenizer

random.seed(2718)

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v70.jsonl"


# Use the same SYSTEM_TEXT and TOOLS as v69 — they're proven to work
import sys
sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, BRIEF, brief, build_messages, build_pipeline, APPS as APPS_V69


# ============================================================================
# EXTENDED APPS POOL — 25 more single-file simple apps for diversity
# ============================================================================
APPS_EXTRA = [
    ("hex-to-rgb", "a hex to rgb color converter", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [h, setH] = useState('#ff0000')\n  const r = parseInt(h.slice(1,3),16); const g = parseInt(h.slice(3,5),16); const b = parseInt(h.slice(5,7),16)\n  return <div><input value={h} onChange={e => setH(e.target.value)} /><div>RGB: {r}, {g}, {b}</div></div>\n}"),
    ]),
    ("password-gen", "a password generator with length slider", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [len, setLen] = useState(12)\n  const [pw, setPw] = useState('')\n  const gen = () => { const c = 'abcdefghijklmnopqrstuvwxyz0123456789'; setPw(Array.from({length: len}, () => c[Math.floor(Math.random()*c.length)]).join('')) }\n  return <div><input type='range' value={len} onChange={e => setLen(+e.target.value)} min={4} max={32} /><div>{len}</div><button onClick={gen}>generate</button><div>{pw}</div></div>\n}"),
    ]),
    ("bmi-calc", "a BMI calculator", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [w, setW] = useState(70)\n  const [h, setH] = useState(170)\n  const bmi = w / Math.pow(h/100, 2)\n  return <div><input type='number' value={w} onChange={e => setW(+e.target.value)} /><input type='number' value={h} onChange={e => setH(+e.target.value)} /><div>BMI: {bmi.toFixed(1)}</div></div>\n}"),
    ]),
    ("char-counter", "a character counter", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [t, setT] = useState('')\n  return <div><textarea value={t} onChange={e => setT(e.target.value)} /><div>Chars: {t.length}, Words: {t.split(/\\s+/).filter(Boolean).length}</div></div>\n}"),
    ]),
    ("rand-quote", "a random quote generator", [
        ("src/App.tsx", "import { useState } from 'react'\nconst Q = ['Be the change.', 'Stay hungry.', 'Just do it.', 'Less is more.']\nexport default function App() {\n  const [q, setQ] = useState(Q[0])\n  return <div><blockquote>{q}</blockquote><button onClick={() => setQ(Q[Math.floor(Math.random()*Q.length)])}>new</button></div>\n}"),
    ]),
    ("guess-num", "a number guessing game", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [target] = useState(Math.floor(Math.random()*100)+1)\n  const [g, setG] = useState('')\n  const [msg, setMsg] = useState('')\n  return <div><input value={g} onChange={e => setG(e.target.value)} /><button onClick={() => { const n = +g; setMsg(n === target ? 'Win!' : n < target ? 'Higher' : 'Lower') }}>guess</button><div>{msg}</div></div>\n}"),
    ]),
    ("rgb-mixer", "an RGB color mixer with sliders", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [r, setR] = useState(128); const [g, setG] = useState(128); const [b, setB] = useState(128)\n  return <div><input type='range' max={255} value={r} onChange={e => setR(+e.target.value)} /><input type='range' max={255} value={g} onChange={e => setG(+e.target.value)} /><input type='range' max={255} value={b} onChange={e => setB(+e.target.value)} /><div style={{background: `rgb(${r},${g},${b})`, width: 100, height: 100}} /></div>\n}"),
    ]),
    ("text-reverse", "a text reverser", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [t, setT] = useState('')\n  return <div><input value={t} onChange={e => setT(e.target.value)} /><div>{t.split('').reverse().join('')}</div></div>\n}"),
    ]),
    ("base64-tool", "a base64 encode/decode tool", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [t, setT] = useState('')\n  return <div><textarea value={t} onChange={e => setT(e.target.value)} /><div>Encoded: {btoa(t || '')}</div></div>\n}"),
    ]),
    ("loan-calc", "a loan payment calculator", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [p, setP] = useState(100000); const [r, setR] = useState(5); const [n, setN] = useState(30)\n  const m = (p * (r/100/12)) / (1 - Math.pow(1+r/100/12, -n*12))\n  return <div><input type='number' value={p} onChange={e => setP(+e.target.value)} /><input type='number' value={r} onChange={e => setR(+e.target.value)} /><input type='number' value={n} onChange={e => setN(+e.target.value)} /><div>Monthly: ${m.toFixed(2)}</div></div>\n}"),
    ]),
    ("emoji-picker", "an emoji picker", [
        ("src/App.tsx", "import { useState } from 'react'\nconst E = ['😀','😎','🚀','🌊','🎉','💡','🔥','⭐','💯','✨']\nexport default function App() {\n  const [s, setS] = useState('')\n  return <div><div>{E.map(e => <button key={e} onClick={() => setS(s + e)}>{e}</button>)}</div><div>{s}</div></div>\n}"),
    ]),
    ("age-calc", "an age calculator from birthdate", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [b, setB] = useState('2000-01-01')\n  const age = Math.floor((Date.now() - new Date(b).getTime()) / (365.25*24*3600*1000))\n  return <div><input type='date' value={b} onChange={e => setB(e.target.value)} /><div>Age: {age}</div></div>\n}"),
    ]),
    ("countdown", "a countdown timer", [
        ("src/App.tsx", "import { useState, useEffect } from 'react'\nexport default function App() {\n  const target = new Date('2027-01-01').getTime()\n  const [now, setNow] = useState(Date.now())\n  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id) }, [])\n  const d = Math.floor((target - now) / 86400000)\n  return <div>Days to 2027: {d}</div>\n}"),
    ]),
    ("word-counter", "a word counter for documents", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [t, setT] = useState('')\n  const words = t.trim().split(/\\s+/).filter(Boolean).length\n  return <div><textarea value={t} onChange={e => setT(e.target.value)} rows={10} /><div>Words: {words}</div></div>\n}"),
    ]),
    ("tip-split", "a tip splitter for groups", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [bill, setBill] = useState(0); const [tip, setTip] = useState(15); const [n, setN] = useState(2)\n  const total = bill * (1 + tip/100); const each = total / n\n  return <div><input type='number' value={bill} onChange={e => setBill(+e.target.value)} /><input type='number' value={tip} onChange={e => setTip(+e.target.value)} /><input type='number' value={n} onChange={e => setN(+e.target.value)} /><div>Each: ${each.toFixed(2)}</div></div>\n}"),
    ]),
]


# ============================================================================
# MULTI-FILE MEDIUM APPS — tests file_write across multiple files
# ============================================================================
APPS_MEDIUM = [
    ("kanban-3col", "a kanban board with todo doing done columns", [
        ("src/App.tsx", "import { useState } from 'react'\nimport Column from './Column'\nexport default function App() {\n  const cards = {todo:['design'],doing:['code'],done:['plan']}\n  return <div style={{display:'flex',gap:'1rem'}}>{['todo','doing','done'].map(c => <Column key={c} name={c} cards={cards[c as keyof typeof cards]} />)}</div>\n}"),
        ("src/Column.tsx", "export default function Column({name, cards}: any) {\n  return <div style={{padding:'1rem',background:'#eee',flex:1}}><h3>{name}</h3>{cards.map((c: string, i: number) => <div key={i}>{c}</div>)}</div>\n}"),
    ]),
    ("recipe-card", "a recipe card with ingredients and steps", [
        ("src/App.tsx", "import Recipe from './Recipe'\nexport default function App() {\n  return <Recipe title='Pancakes' ingredients={['flour', 'milk', 'eggs']} steps={['mix', 'cook', 'serve']} />\n}"),
        ("src/Recipe.tsx", "export default function Recipe({title, ingredients, steps}: any) {\n  return <div><h1>{title}</h1><h2>Ingredients</h2><ul>{ingredients.map((i:string,k:number)=><li key={k}>{i}</li>)}</ul><h2>Steps</h2><ol>{steps.map((s:string,k:number)=><li key={k}>{s}</li>)}</ol></div>\n}"),
    ]),
    ("flashcards", "a flashcard study app", [
        ("src/App.tsx", "import { useState } from 'react'\nimport Card from './Card'\nconst CARDS = [{q:'2+2', a:'4'}, {q:'capital of France', a:'Paris'}]\nexport default function App() {\n  const [i, setI] = useState(0)\n  return <div><Card q={CARDS[i].q} a={CARDS[i].a} /><button onClick={() => setI((i+1) % CARDS.length)}>next</button></div>\n}"),
        ("src/Card.tsx", "import { useState } from 'react'\nexport default function Card({q, a}: any) {\n  const [show, setShow] = useState(false)\n  return <div onClick={() => setShow(!show)}>{show ? a : q}</div>\n}"),
    ]),
    ("pomodoro-multi", "a pomodoro timer with separate timer and controls", [
        ("src/App.tsx", "import { useState, useEffect } from 'react'\nimport Timer from './Timer'\nimport Controls from './Controls'\nexport default function App() {\n  const [s, setS] = useState(1500); const [run, setRun] = useState(false)\n  useEffect(() => { if (!run) return; const i = setInterval(() => setS(x => x > 0 ? x-1 : 0), 1000); return () => clearInterval(i) }, [run])\n  return <div><Timer seconds={s} /><Controls running={run} onToggle={() => setRun(!run)} onReset={() => setS(1500)} /></div>\n}"),
        ("src/Timer.tsx", "export default function Timer({seconds}: any) {\n  const m = Math.floor(seconds/60); const s = seconds%60\n  return <div>{m}:{String(s).padStart(2, '0')}</div>\n}"),
        ("src/Controls.tsx", "export default function Controls({running, onToggle, onReset}: any) {\n  return <div><button onClick={onToggle}>{running ? 'pause' : 'start'}</button><button onClick={onReset}>reset</button></div>\n}"),
    ]),
    ("expense-list", "an expense tracker with list and total", [
        ("src/App.tsx", "import { useState } from 'react'\nimport ExpenseForm from './ExpenseForm'\nimport ExpenseList from './ExpenseList'\nexport default function App() {\n  const [items, setItems] = useState<any[]>([])\n  const total = items.reduce((s, i) => s + i.amount, 0)\n  return <div><h1>Expenses</h1><ExpenseForm onAdd={(e:any) => setItems([...items, e])} /><ExpenseList items={items} /><div>Total: ${total.toFixed(2)}</div></div>\n}"),
        ("src/ExpenseForm.tsx", "import { useState } from 'react'\nexport default function ExpenseForm({onAdd}: any) {\n  const [n, setN] = useState(''); const [a, setA] = useState(0)\n  return <form onSubmit={e => { e.preventDefault(); onAdd({name: n, amount: a}); setN(''); setA(0) }}><input value={n} onChange={e => setN(e.target.value)} /><input type='number' value={a} onChange={e => setA(+e.target.value)} /><button type='submit'>add</button></form>\n}"),
        ("src/ExpenseList.tsx", "export default function ExpenseList({items}: any) {\n  return <ul>{items.map((i:any, k:number) => <li key={k}>{i.name}: ${i.amount}</li>)}</ul>\n}"),
    ]),
]


# ============================================================================
# MULTI-TOOL-CALL EXAMPLES — single assistant turn, multiple tool calls
# Tests Gemma 4's ability to fire multiple tools in one response
# ============================================================================
def build_multi_tool_call_messages(user_prompt, multi_calls_groups):
    """multi_calls_groups: list of (calls, responses) tuples.
    calls = [(name, args), ...] for parallel tool_calls in one assistant turn
    responses = [resp1, resp2, ...] matching each call's response (each as own tool turn)
    """
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
    ]
    for calls, responses in multi_calls_groups:
        # Single assistant turn with multiple tool_calls
        messages.append({
            "role": "assistant",
            "content": brief(calls[0][0]),
            "tool_calls": [
                {"type": "function", "function": {"name": n, "arguments": a}}
                for n, a in calls
            ],
        })
        # Each tool response is a separate tool turn
        for (n, _), r in zip(calls, responses):
            messages.append({"role": "tool", "name": n, "content": (r[:500] if r else "OK")})
    return messages


def build_multi_tool_call_pipeline(name, desc, files):
    """Pipeline using a multi-tool-call assistant turn for the file_writes."""
    user_prompt = f"Build me {desc}."
    groups = []

    # Group 1: project_init alone (single call)
    groups.append((
        [("project_init", {"name": name})],
        [f"Created project deliverables/{name}"]
    ))

    # Group 2: ALL file_writes in ONE assistant turn (multi-tool-call!)
    write_calls = [("file_write", {"path": p, "content": c}) for p, c in files]
    write_responses = [f"Wrote {p}" for p, _ in files]
    groups.append((write_calls, write_responses))

    # Group 3: shell_exec build (single)
    groups.append((
        [("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"})],
        ["vite v5.0.0 building... built in 1.23s"]
    ))

    # Group 4: undertow (single)
    groups.append((
        [("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc})],
        ["Screenshot taken. App renders correctly."]
    ))

    # Group 5: message_result (single)
    groups.append((
        [("message_result", {"text": f"Built {name}: {desc}. Ready in deliverables/{name}."})],
        ["Delivered."]
    ))

    return build_multi_tool_call_messages(user_prompt, groups)


# ============================================================================
# L3 RECOVERY — multi-turn error recovery in NEW format
# user("Fix it") + assistant(shell_exec build) + tool(error) + assistant(file_edit)
# ============================================================================
L3_TYPE_ERRORS = [
    ("Type error: Type 'null' is not assignable to type 'string'. setError(null)",
     "deliverables/app/src/App.tsx", "setError(null)", "setError('')"),
    ("Type error: Type 'string' is not assignable to type 'number'. count: '0'",
     "deliverables/app/src/components/Counter.tsx", "count: '0'", "count: 0"),
    ("Type error: Property 'value' is missing in type '{}' but required",
     "deliverables/app/src/App.tsx", "<Component />", "<Component value=\"\" />"),
]
L3_SYNTAX_ERRORS = [
    ("Syntax error: ')' expected. items.map(i => <div>{i}</div>",
     "deliverables/app/src/App.tsx", "items.map(i => <div>{i}</div>", "items.map(i => <div>{i}</div>)"),
    ("Syntax error: '}' expected. return <div>{children",
     "deliverables/app/src/components/List.tsx", "{children", "{children}"),
]
L3_CSS_ERRORS = [
    ("Could not resolve 'leaflet/dist/leaflet.css' from src/App.tsx",
     "deliverables/app/src/App.tsx", "import 'leaflet/dist/leaflet.css'", "// removed unused import"),
]


def build_l3_recovery(error_text, path, old, new):
    """L3 multi-turn recovery example."""
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": "The build just failed. Fix it."},
        {"role": "assistant", "content": brief("shell_exec"), "tool_calls": [
            {"type": "function", "function": {"name": "shell_exec",
             "arguments": {"command": "cd deliverables/app && npx vite build"}}}
        ]},
        {"role": "tool", "name": "shell_exec", "content": f"[shell_exec] Error: {error_text}"},
        {"role": "assistant", "content": brief("file_edit"), "tool_calls": [
            {"type": "function", "function": {"name": "file_edit",
             "arguments": {"path": path, "old_text": old, "new_text": new}}}
        ]},
        {"role": "tool", "name": "file_edit", "content": f"[file_edit] replaced in {path}"},
    ]
    return messages


# ============================================================================
# L4 RESEARCH-FIRST (HF02) — novel tech request → search_web
# ============================================================================
L4_RESEARCH_CASES = [
    ("Build something using the new React Server Components", "react server components 2026 tutorial"),
    ("Build with the new Vercel AI SDK v6", "vercel ai sdk v6 tutorial"),
    ("Build a demo of CSS anchor positioning", "css anchor positioning 2026"),
    ("Build using Bun's new fullstack framework", "bun fullstack framework 2026"),
]


def build_l4_research(user_prompt, query):
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": brief("search_web"), "tool_calls": [
            {"type": "function", "function": {"name": "search_web",
             "arguments": {"query": query, "num_results": 5}}}
        ]},
        {"role": "tool", "name": "search_web", "content": "Results: 1. Official docs... 2. Tutorial..."},
    ]
    return messages


# ============================================================================
# L4 PLAN-FIRST (HF09) — explicitly complex request → plan_update
# ============================================================================
L4_PLAN_CASES = [
    ("Build a multi-step form wizard with validation. This needs careful planning — multiple steps, state management, validation rules.",
     "Build form wizard with validation",
     ["scaffold", "form components", "validation", "state", "deliver"]),
    ("Build a Spotify-style music player with playlists and search. Plan carefully — many components and complex state.",
     "Build music player with playlists",
     ["scaffold", "player core", "playlist", "search", "deliver"]),
    ("Build a video conferencing UI with multiple participants. Complex — needs careful planning.",
     "Build video conf UI",
     ["scaffold", "video grid", "controls", "chat", "deliver"]),
]


def build_l4_plan(user_prompt, goal, phases):
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": brief("plan_update"), "tool_calls": [
            {"type": "function", "function": {"name": "plan_update",
             "arguments": {"goal": goal, "phases": phases}}}
        ]},
        {"role": "tool", "name": "plan_update", "content": "Plan accepted with 5 phases"},
    ]
    return messages


# ============================================================================
# L4 DEDUP-GUARD (HF08) — existing project → project_init (re-scaffold)
# ============================================================================
L4_DEDUP_CASES = [
    ("pomodoro-timer", "a pomodoro timer with sessions"),
    ("calculator-dark", "a calculator with dark theme"),
    ("todo-app", "a todo app with categories"),
]


def build_l4_dedup(name, desc):
    user_prompt = (f"Build {desc}\n\n[EXISTING PROJECT: {name}]\n"
                   f"Path: deliverables/{name}\nStatus: BROKEN — won't compile\n"
                   f"Re-initialize and fix.")
    messages = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": brief("project_init"), "tool_calls": [
            {"type": "function", "function": {"name": "project_init",
             "arguments": {"name": name}}}
        ]},
        {"role": "tool", "name": "project_init", "content": f"Re-scaffolded deliverables/{name}"},
    ]
    return messages


# ============================================================================
# MAIN
# ============================================================================
def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    examples = []

    # 10 v69 simple apps + 15 extra simple apps = 25 simple
    all_simple = APPS_V69 + APPS_EXTRA
    for name, desc, files in all_simple:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 5 medium multi-file apps
    for name, desc, files in APPS_MEDIUM:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 5 multi-tool-call examples (using a subset of medium apps)
    for name, desc, files in APPS_MEDIUM[:5]:
        # Re-render with multi-tool-call structure
        msgs = build_multi_tool_call_pipeline(name + "-multi", desc, files)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 6 L3 recovery examples
    for err in L3_TYPE_ERRORS:
        msgs = build_l3_recovery(*err)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})
    for err in L3_SYNTAX_ERRORS:
        msgs = build_l3_recovery(*err)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})
    for err in L3_CSS_ERRORS:
        msgs = build_l3_recovery(*err)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 4 L4 research-first
    for user, query in L4_RESEARCH_CASES:
        msgs = build_l4_research(user, query)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 3 L4 plan-first
    for user, goal, phases in L4_PLAN_CASES:
        msgs = build_l4_plan(user, goal, phases)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 3 L4 dedup-guard
    for name, desc in L4_DEDUP_CASES:
        msgs = build_l4_dedup(name, desc)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"\nGenerated {len(examples)} examples:")
    print(f"  - 25 simple apps")
    print(f"  - 5 medium multi-file apps")
    print(f"  - 5 multi-tool-call apps")
    print(f"  - 6 L3 multi-turn recovery")
    print(f"  - 4 L4 research-first")
    print(f"  - 3 L4 plan-first")
    print(f"  - 3 L4 dedup-guard")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nWrote {len(examples)} examples to {OUT_PATH}")

    # Validation: all start with <bos>?
    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"\nStarts with <bos>: {starts_bos}/{len(examples)}")


if __name__ == "__main__":
    main()
