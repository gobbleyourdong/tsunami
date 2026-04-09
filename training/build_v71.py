#!/usr/bin/env python3
"""v71 — procedural coverage fix per other-instance analysis.

THE INSIGHT (other instance):
  L1/L2/L5 come "free" from any well-formatted complete example.
  L3/L4 need DEDICATED procedural examples that don't fall out of happy paths.
  v69's 10 happy-path examples gave us L5=78% but L3=33% L4=60%.

v71 composition (per recommendation):
  - 60% happy-path (480 examples) — diverse APPS pool, multiple variations
  - 25% recovery (200 examples) — error → read → rewrite/edit → rebuild
  - 15% L4 patterns (120 examples) — research-first, plan-first, undertow, refusals
  Total: ~800 examples

All use tokenizer.apply_chat_template() — same proven format as v69.
"""
import json
import os
import random

from transformers import AutoTokenizer

random.seed(8888)

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v71.jsonl"


import sys
sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, BRIEF, brief, build_messages, build_pipeline
from build_v69 import APPS as APPS_V69
from build_v70 import APPS_EXTRA as APPS_V70_EXTRA
from build_v70 import APPS_MEDIUM as APPS_V70_MEDIUM


# ============================================================================
# EXPANDED APP POOL — many more single-file simple apps
# ============================================================================
APPS_BIG = [
    ("notes-app", "a notes app with add and view", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [n, setN] = useState<string[]>([])\n  const [v, setV] = useState('')\n  return <div><textarea value={v} onChange={e => setV(e.target.value)} /><button onClick={() => { if (v) { setN([...n, v]); setV('') } }}>save</button><ul>{n.map((x, i) => <li key={i}>{x}</li>)}</ul></div>\n}"),
    ]),
    ("calorie-tracker", "a calorie tracker for meals", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [m, setM] = useState<{name:string,cal:number}[]>([])\n  const [n, setN] = useState(''); const [c, setC] = useState(0)\n  const total = m.reduce((s, x) => s + x.cal, 0)\n  return <div><input value={n} onChange={e => setN(e.target.value)} /><input type='number' value={c} onChange={e => setC(+e.target.value)} /><button onClick={() => { setM([...m, {name:n, cal:c}]); setN(''); setC(0) }}>add</button><div>Total: {total}</div></div>\n}"),
    ]),
    ("habit-tracker", "a daily habit tracker", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [h, setH] = useState<{name:string, done:boolean}[]>([{name:'water', done:false}])\n  return <div>{h.map((x, i) => <div key={i}><input type='checkbox' checked={x.done} onChange={() => setH(h.map((y,j) => j===i ? {...y, done:!y.done} : y))} /> {x.name}</div>)}</div>\n}"),
    ]),
    ("expense-simple", "a simple expense logger", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [e, setE] = useState<number[]>([])\n  const [v, setV] = useState(0)\n  return <div><input type='number' value={v} onChange={ev => setV(+ev.target.value)} /><button onClick={() => setE([...e, v])}>add</button><div>Total: {e.reduce((s,x)=>s+x,0)}</div></div>\n}"),
    ]),
    ("todo-priority", "a todo list with priority", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [t, setT] = useState<{text:string, p:string}[]>([])\n  const [v, setV] = useState(''); const [p, setP] = useState('low')\n  return <div><input value={v} onChange={e => setV(e.target.value)} /><select value={p} onChange={e => setP(e.target.value)}><option>low</option><option>med</option><option>high</option></select><button onClick={() => { setT([...t, {text:v, p}]); setV('') }}>add</button><ul>{t.map((x, i) => <li key={i}>[{x.p}] {x.text}</li>)}</ul></div>\n}"),
    ]),
    ("game-rps", "a rock paper scissors game", [
        ("src/App.tsx", "import { useState } from 'react'\nconst C = ['rock', 'paper', 'scissors']\nexport default function App() {\n  const [p, setP] = useState(''); const [c, setC] = useState(''); const [r, setR] = useState('')\n  const play = (x: string) => { const cc = C[Math.floor(Math.random()*3)]; setP(x); setC(cc); setR(x === cc ? 'tie' : (x === 'rock' && cc === 'scissors') || (x === 'paper' && cc === 'rock') || (x === 'scissors' && cc === 'paper') ? 'win' : 'lose') }\n  return <div>{C.map(x => <button key={x} onClick={() => play(x)}>{x}</button>)}<div>You: {p} | CPU: {c} | {r}</div></div>\n}"),
    ]),
    ("clock-world", "a world clock for multiple cities", [
        ("src/App.tsx", "import { useState, useEffect } from 'react'\nconst CITIES = [['Tokyo', 9], ['London', 0], ['NYC', -5]]\nexport default function App() {\n  const [t, setT] = useState(new Date())\n  useEffect(() => { const i = setInterval(() => setT(new Date()), 1000); return () => clearInterval(i) }, [])\n  return <div>{CITIES.map(([c, o]) => <div key={c as string}>{c as string}: {new Date(t.getTime() + (o as number)*3600000).toUTCString().slice(17, 25)}</div>)}</div>\n}"),
    ]),
    ("converter-units", "a unit converter (km/miles)", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [km, setKm] = useState(0)\n  return <div><input type='number' value={km} onChange={e => setKm(+e.target.value)} /><div>{km} km = {(km * 0.621371).toFixed(2)} miles</div></div>\n}"),
    ]),
    ("link-tree", "a personal links page", [
        ("src/App.tsx", "const LINKS = [{label: 'GitHub', url: 'https://github.com'}, {label: 'Twitter', url: 'https://twitter.com'}, {label: 'Blog', url: 'https://example.com'}]\nexport default function App() {\n  return <div><h1>My Links</h1>{LINKS.map(l => <div key={l.url}><a href={l.url}>{l.label}</a></div>)}</div>\n}"),
    ]),
    ("todo-localstorage", "a todo list with localStorage", [
        ("src/App.tsx", "import { useState, useEffect } from 'react'\nexport default function App() {\n  const [t, setT] = useState<string[]>(() => JSON.parse(localStorage.getItem('todos') || '[]'))\n  useEffect(() => localStorage.setItem('todos', JSON.stringify(t)), [t])\n  const [v, setV] = useState('')\n  return <div><input value={v} onChange={e => setV(e.target.value)} /><button onClick={() => { setT([...t, v]); setV('') }}>add</button><ul>{t.map((x,i)=><li key={i}>{x}</li>)}</ul></div>\n}"),
    ]),
    ("price-tag", "a price calculator with tax", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [p, setP] = useState(0); const [t, setT] = useState(8.5)\n  const total = p * (1 + t/100)\n  return <div><input type='number' value={p} onChange={e => setP(+e.target.value)} /><input type='number' value={t} onChange={e => setT(+e.target.value)} /><div>Total: ${total.toFixed(2)}</div></div>\n}"),
    ]),
    ("text-uppercase", "a text case converter", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [t, setT] = useState('')\n  return <div><input value={t} onChange={e => setT(e.target.value)} /><div>UPPER: {t.toUpperCase()}</div><div>lower: {t.toLowerCase()}</div></div>\n}"),
    ]),
    ("number-formatter", "a number formatter for large numbers", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [n, setN] = useState(1234567)\n  return <div><input type='number' value={n} onChange={e => setN(+e.target.value)} /><div>{n.toLocaleString()}</div></div>\n}"),
    ]),
    ("rating-stars", "a 5-star rating widget", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [r, setR] = useState(0)\n  return <div>{[1,2,3,4,5].map(i => <span key={i} onClick={() => setR(i)} style={{cursor:'pointer'}}>{i <= r ? '⭐' : '☆'}</span>)}<div>Rating: {r}/5</div></div>\n}"),
    ]),
    ("progress-bar", "a progress bar with percentage", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [p, setP] = useState(50)\n  return <div><input type='range' value={p} onChange={e => setP(+e.target.value)} /><div style={{background:'#eee', width:'100%', height: 20}}><div style={{background:'blue', width:`${p}%`, height:'100%'}} /></div><div>{p}%</div></div>\n}"),
    ]),
    ("dark-mode-toggle", "a dark mode toggle", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [d, setD] = useState(false)\n  return <div style={{background: d ? '#222' : '#fff', color: d ? '#fff' : '#222', padding: 20, minHeight: '100vh'}}><button onClick={() => setD(!d)}>{d ? 'light' : 'dark'}</button><h1>Hello {d ? 'night' : 'day'}</h1></div>\n}"),
    ]),
    ("tab-switcher", "a tab switcher with 3 tabs", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [t, setT] = useState(0)\n  const tabs = ['Home', 'About', 'Contact']\n  return <div><div>{tabs.map((x, i) => <button key={i} onClick={() => setT(i)} style={{fontWeight: t===i ? 'bold' : 'normal'}}>{x}</button>)}</div><div>{tabs[t]} content</div></div>\n}"),
    ]),
    ("modal-popup", "a modal popup component", [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [open, setOpen] = useState(false)\n  return <div><button onClick={() => setOpen(true)}>open</button>{open && <div style={{position:'fixed', inset:0, background:'rgba(0,0,0,0.5)'}}><div style={{background:'white', padding:20, margin:'20vh auto', width:300}}><h2>Modal</h2><button onClick={() => setOpen(false)}>close</button></div></div>}</div>\n}"),
    ]),
    ("accordion", "an FAQ accordion", [
        ("src/App.tsx", "import { useState } from 'react'\nconst FAQ = [{q:'What?', a:'Answer 1'}, {q:'Why?', a:'Answer 2'}, {q:'How?', a:'Answer 3'}]\nexport default function App() {\n  const [open, setOpen] = useState(-1)\n  return <div>{FAQ.map((f, i) => <div key={i}><div onClick={() => setOpen(open === i ? -1 : i)}>{f.q}</div>{open === i && <div>{f.a}</div>}</div>)}</div>\n}"),
    ]),
    ("rainbow-text", "rainbow gradient text", [
        ("src/App.tsx", "export default function App() {\n  return <h1 style={{background:'linear-gradient(90deg, red, orange, yellow, green, blue, indigo, violet)', WebkitBackgroundClip:'text', color:'transparent', fontSize:60}}>Rainbow!</h1>\n}"),
    ]),
]


# ============================================================================
# RECOVERY SCENARIO DATA
# Each scenario: (app_name, app_desc, broken_files, error_msg, fix_pattern)
# fix_pattern: 'rewrite' (file_write full), 'edit' (file_edit), 'install' (npm), 'cd' (path)
# ============================================================================
RECOVERY_SCENARIOS = [
    # Type errors → file_edit (small fix)
    {
        "name": "counter-type",
        "desc": "a counter app",
        "files": [("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [c, setC] = useState<string>(0)\n  return <button onClick={() => setC(c + 1)}>{c}</button>\n}")],
        "error": "src/App.tsx(3,30): Type '0' is not assignable to type 'string'.",
        "fix_path": "src/App.tsx",
        "fix_old": "useState<string>(0)",
        "fix_new": "useState<number>(0)",
        "fix_type": "edit",
    },
    {
        "name": "form-type",
        "desc": "a form input",
        "files": [("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [v, setV] = useState<number>('')\n  return <input value={v} onChange={e => setV(e.target.value)} />\n}")],
        "error": "src/App.tsx(3,29): Type 'string' is not assignable to type 'number'.",
        "fix_path": "src/App.tsx",
        "fix_old": "useState<number>('')",
        "fix_new": "useState<string>('')",
        "fix_type": "edit",
    },
    # Syntax errors → file_edit
    {
        "name": "list-syntax",
        "desc": "a list",
        "files": [("src/App.tsx", "export default function App() {\n  const items = [1, 2, 3]\n  return <ul>{items.map(i => <li>{i}</li>}</ul>\n}")],
        "error": "src/App.tsx(3,42): ')' expected.",
        "fix_path": "src/App.tsx",
        "fix_old": "items.map(i => <li>{i}</li>}",
        "fix_new": "items.map(i => <li>{i}</li>)}",
        "fix_type": "edit",
    },
    # Missing module → shell_exec npm install
    {
        "name": "chart-module",
        "desc": "a chart with recharts",
        "files": [("src/App.tsx", "import { LineChart, Line } from 'recharts'\nexport default function App() {\n  return <LineChart width={400} height={300} data={[]}><Line dataKey='v' /></LineChart>\n}")],
        "error": "Cannot find module 'recharts'. Did you install it?",
        "fix_cmd": "npm install recharts",
        "fix_type": "install",
    },
    {
        "name": "router-module",
        "desc": "a routed app",
        "files": [("src/App.tsx", "import { BrowserRouter } from 'react-router-dom'\nexport default function App() {\n  return <BrowserRouter><div>routed</div></BrowserRouter>\n}")],
        "error": "Cannot find module 'react-router-dom'.",
        "fix_cmd": "npm install react-router-dom",
        "fix_type": "install",
    },
    # Missing file → file_write (create new)
    {
        "name": "header-missing",
        "desc": "an app with header",
        "files": [("src/App.tsx", "import Header from './Header'\nexport default function App() {\n  return <div><Header /><h1>App</h1></div>\n}")],
        "error": "Could not resolve './Header' from src/App.tsx. File does not exist.",
        "fix_path": "src/Header.tsx",
        "fix_content": "export default function Header() {\n  return <header><h1>Header</h1></header>\n}",
        "fix_type": "create",
    },
    # Wrong path → shell_exec with corrected path
    {
        "name": "cd-fail",
        "desc": "an app",
        "files": [("src/App.tsx", "export default function App() { return <div>app</div> }")],
        "wrong_cmd": "cd workspace/deliverables/app && npx vite build",
        "error": "bash: cd: workspace/deliverables/app: No such file or directory",
        "fix_cmd": "cd deliverables/app && npx vite build",
        "fix_type": "cd",
    },
    # Bigger structural fix → full file_write rewrite
    {
        "name": "broken-app-rewrite",
        "desc": "a counter",
        "files": [("src/App.tsx", "import { useState } from 'react'\nexport default function App {\n  const [c, setC] = useState(0)\n  return <button onClick={() => setC(c + 1)}>{c}</button>\n}")],
        "error": "src/App.tsx(2,29): Identifier expected. Function declarations require parentheses.",
        "fix_path": "src/App.tsx",
        "fix_content": "import { useState } from 'react'\nexport default function App() {\n  const [c, setC] = useState(0)\n  return <button onClick={() => setC(c + 1)}>{c}</button>\n}",
        "fix_type": "rewrite",
    },
]


def build_recovery_pipeline(scenario):
    """Build full pipeline with deliberate failure → recovery → success."""
    name = scenario["name"]
    desc = scenario["desc"]
    files = scenario["files"]
    fix_type = scenario["fix_type"]

    user_prompt = f"Build me {desc}."
    turns = []

    # 1. project_init
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))

    # 2. file_write (with deliberate bug)
    for path, content in files:
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))

    # 3. shell_exec — first build attempt FAILS
    if fix_type == "cd":
        # Special: wrong cd command
        turns.append(("shell_exec", {"command": scenario["wrong_cmd"]},
                      f"Error: {scenario['error']}"))
    else:
        turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                      f"Error: {scenario['error']}"))

    # 4. Recovery action — varies by fix_type
    if fix_type == "edit":
        # Read first to diagnose, then file_edit
        turns.append(("file_read", {"path": scenario["fix_path"]},
                      f"// {scenario['fix_path']} (current contents)"))
        turns.append(("file_edit", {
            "path": scenario["fix_path"],
            "old_text": scenario["fix_old"],
            "new_text": scenario["fix_new"],
        }, f"Replaced in {scenario['fix_path']}"))
    elif fix_type == "rewrite":
        # Read first to diagnose, then file_write rewrite
        turns.append(("file_read", {"path": scenario["fix_path"]},
                      f"// {scenario['fix_path']} (broken contents)"))
        turns.append(("file_write", {
            "path": scenario["fix_path"],
            "content": scenario["fix_content"],
        }, f"Rewrote {scenario['fix_path']}"))
    elif fix_type == "create":
        # Create the missing file
        turns.append(("file_write", {
            "path": scenario["fix_path"],
            "content": scenario["fix_content"],
        }, f"Created {scenario['fix_path']}"))
    elif fix_type == "install":
        # npm install the missing module
        turns.append(("shell_exec", {"command": f"cd deliverables/{name} && {scenario['fix_cmd']}"},
                      f"added 1 package"))
    elif fix_type == "cd":
        # Re-run with correct path
        turns.append(("shell_exec", {"command": scenario["fix_cmd"]},
                      "vite v5.0.0 building... built in 1.23s"))

    # 5. Final build (success)
    if fix_type != "cd":  # cd already includes the build
        turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                      "vite v5.0.0 building... built in 1.34s"))

    # 6. undertow QA
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Screenshot taken. App renders correctly."))

    # 7. message_result
    turns.append(("message_result", {"text": f"Built {name}: {desc}. Ready in deliverables/{name}."},
                  "Delivered."))

    return build_messages(user_prompt, turns)


# ============================================================================
# L4 PATTERNS — research-first, plan-first, undertow-always, refusals
# ============================================================================

def build_research_first(novel_request, query, app_name, app_desc, files):
    """User asks for novel tech → search_web first → then build."""
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
    turns.append(("message_result", {"text": f"Researched and built {app_name}."}, "Delivered."))
    return build_messages(user_prompt, turns)


def build_plan_first(complex_request, goal, phases, app_name, app_desc, files):
    """Complex multi-step request → plan_update first → then build."""
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
    turns.append(("message_result", {"text": f"Executed plan, built {app_name}."}, "Delivered."))
    return build_messages(user_prompt, turns)


# ============================================================================
# DATA POOLS
# ============================================================================
NOVEL_TECH_REQUESTS = [
    ("Build something using the new React Server Components", "react server components 2026 tutorial",
     "rsc-demo", "an RSC demo"),
    ("Build a demo of the new View Transitions API", "view transitions api 2026 react",
     "view-transitions", "a view transitions demo"),
    ("Build with the latest Tailwind v5 features", "tailwind v5 features 2026",
     "tailwind-v5", "a Tailwind v5 demo"),
    ("Build using the Web USB API", "web usb api browser 2026",
     "webusb-demo", "a Web USB demo"),
    ("Build with Bun's new fullstack framework", "bun fullstack framework 2026",
     "bun-app", "a Bun fullstack app"),
    ("Build using the new CSS @scope rules", "css scope rules 2026",
     "css-scope", "a CSS scope demo"),
    ("Build a demo of WebGPU compute shaders", "webgpu compute shaders 2026",
     "webgpu-compute", "a WebGPU compute demo"),
    ("Build using HTMX 2.0 hypermedia patterns", "htmx 2.0 patterns 2026",
     "htmx-demo", "an HTMX demo"),
    ("Build a demo of CSS anchor positioning", "css anchor positioning 2026",
     "anchor-demo", "an anchor positioning demo"),
    ("Build something with the new Notion API v3", "notion api v3 react 2026",
     "notion-app", "a Notion API demo"),
]


PLAN_FIRST_REQUESTS = [
    ("Build a multi-step form wizard with validation, state management, and 5 steps. This is complex — plan carefully.",
     "Build form wizard with validation",
     ["scaffold", "form components", "validation rules", "state management", "deliver"],
     "form-wizard", "a multi-step form wizard"),
    ("Build a Spotify-style music player with playlists, search, and audio controls. Plan needed.",
     "Build music player with playlists",
     ["scaffold", "player UI", "playlist", "search", "deliver"],
     "music-player", "a music player UI"),
    ("Build a video conferencing UI with participants, controls, chat. Complex layout.",
     "Build video conf UI",
     ["scaffold", "video grid", "controls", "chat", "deliver"],
     "video-conf", "a video conferencing UI"),
    ("Build a Notion-style nested document editor. This needs careful planning.",
     "Build nested doc editor",
     ["scaffold", "block components", "nesting logic", "editor", "deliver"],
     "doc-editor", "a nested document editor"),
    ("Build a calendar app with month, week, day views and event scheduling. Plan first.",
     "Build calendar with multiple views",
     ["scaffold", "calendar grid", "month view", "events", "deliver"],
     "calendar-multi", "a calendar with multiple views"),
    ("Build a kanban board with drag-drop, columns, cards, and storage. Plan needed.",
     "Build kanban with drag-drop",
     ["scaffold", "board", "drag handlers", "storage", "deliver"],
     "kanban-dnd", "a kanban with drag-drop"),
    ("Build a dashboard with multiple charts, filters, and a sidebar. Complex.",
     "Build dashboard with charts",
     ["scaffold", "sidebar", "charts", "filters", "deliver"],
     "dashboard-multi", "a multi-chart dashboard"),
    ("Build a real-time chat app with rooms, users, and message history. Plan it.",
     "Build chat with rooms",
     ["scaffold", "rooms", "messages", "history", "deliver"],
     "chat-rooms", "a chat with rooms"),
]


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    examples = []

    # ============================================================
    # 1. HAPPY PATH (60% = ~480 examples)
    # Pool: 10 v69 + 15 v70 + 20 new = 45 unique apps
    # Sample with replacement to reach ~480 examples
    # ============================================================
    all_simple_apps = APPS_V69 + APPS_V70_EXTRA + APPS_BIG  # 45 apps
    print(f"Simple app pool: {len(all_simple_apps)}")

    HAPPY_TARGET = 480
    happy_count = 0
    while happy_count < HAPPY_TARGET:
        for app in all_simple_apps:
            if happy_count >= HAPPY_TARGET:
                break
            name, desc, files = app
            # Vary the project name slightly to add diversity
            varied_name = name if happy_count // len(all_simple_apps) == 0 else f"{name}-{happy_count // len(all_simple_apps)}"
            msgs = build_pipeline(varied_name, desc, files, parallel=False)
            text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
            examples.append({"text": text})
            happy_count += 1

    # Add 5 multi-file medium apps
    for app in APPS_V70_MEDIUM:
        name, desc, files = app
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    print(f"Happy path: {happy_count + len(APPS_V70_MEDIUM)} examples")

    # ============================================================
    # 2. RECOVERY (25% = ~200 examples)
    # 8 base scenarios × ~25 variations = 200
    # ============================================================
    RECOVERY_TARGET = 200
    recovery_count = 0
    while recovery_count < RECOVERY_TARGET:
        for scenario in RECOVERY_SCENARIOS:
            if recovery_count >= RECOVERY_TARGET:
                break
            # Vary the project name slightly
            varied = dict(scenario)
            varied["name"] = f"{scenario['name']}-{recovery_count // len(RECOVERY_SCENARIOS)}"
            msgs = build_recovery_pipeline(varied)
            text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
            examples.append({"text": text})
            recovery_count += 1
    print(f"Recovery: {recovery_count} examples")

    # ============================================================
    # 3. L4 PATTERNS (15% = ~120 examples)
    # Research-first: 60
    # Plan-first: 60
    # ============================================================
    L4_RESEARCH_TARGET = 60
    L4_PLAN_TARGET = 60

    # Generic 1-file content for L4 examples
    GENERIC_FILES = [
        ("src/App.tsx", "import { useState } from 'react'\nexport default function App() {\n  const [v, setV] = useState(0)\n  return <div>{v}<button onClick={() => setV(v+1)}>+</button></div>\n}"),
    ]

    research_count = 0
    while research_count < L4_RESEARCH_TARGET:
        for req, query, name, desc in NOVEL_TECH_REQUESTS:
            if research_count >= L4_RESEARCH_TARGET:
                break
            varied_name = f"{name}-{research_count // len(NOVEL_TECH_REQUESTS)}"
            msgs = build_research_first(req, query, varied_name, desc, GENERIC_FILES)
            text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
            examples.append({"text": text})
            research_count += 1

    plan_count = 0
    while plan_count < L4_PLAN_TARGET:
        for req, goal, phases, name, desc in PLAN_FIRST_REQUESTS:
            if plan_count >= L4_PLAN_TARGET:
                break
            varied_name = f"{name}-{plan_count // len(PLAN_FIRST_REQUESTS)}"
            msgs = build_plan_first(req, goal, phases, varied_name, desc, GENERIC_FILES)
            text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
            examples.append({"text": text})
            plan_count += 1

    print(f"L4 research-first: {research_count}, plan-first: {plan_count}")

    print(f"\nTotal: {len(examples)} examples")

    # Validate all start with <bos>
    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"Starts with <bos>: {starts_bos}/{len(examples)}")

    # Shuffle for variety in training
    random.shuffle(examples)

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
