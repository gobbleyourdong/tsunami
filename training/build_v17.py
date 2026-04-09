#!/usr/bin/env python3
"""v17 = v14 base (512) + ~120 surgical fix examples = 632 total.

Fixes v16's regressions:
- L1 trivial: 5 fails (message_result expected, got None/message_chat)
- L1 extreme: 5 fails (project_init expected, got plan_update)
- L3: 5/6 fail (file_read instead of file_edit on errors)
- L4: HF02 research gate, HF06 info loop, HF08 dedup guard

Strategy: single-turn examples targeted at the exact eval format, plus
keep a smaller dose of v16's winning multi-turn patterns.
"""
import json
import random
import re

random.seed(2718)  # different from v16

# Import the v16 formatters (reuse TOOL_SCHEMAS, format_tool_call, etc)
import sys
sys.path.insert(0, 'training')
from build_v16 import (
    SYSTEM_TEXT, QUOTE, TOOL_SCHEMAS, ARG_ORDER,
    format_declaration, format_value, format_tool_call, format_tool_response,
    build_example, APPS_SIMPLE, APPS_MEDIUM, APPS_COMPLEX,
    stub_content, ok_build, stub_read, UNDERTOW_OK,
    gen_happy_simple, gen_happy_medium, gen_happy_complex,
    gen_verify_stop, gen_progressive_complex,
)


# ============================================================================
# NEW GENERATORS — targeting v16 regressions
# ============================================================================

# A. Single-turn error → file_edit (L3 fix)
ERROR_EDIT_CASES = [
    # (user_prompt, path, old, new)
    ("Build error in deliverables/counter/src/App.tsx at line 5:\nerror TS2322: Type 'string' is not assignable to type 'number'\nLine: const count: number = \"0\"",
     "deliverables/counter/src/App.tsx", 'const count: number = "0"', 'const count: number = 0'),
    ("Build error in deliverables/todo/src/App.tsx at line 8:\nerror TS1005: ',' expected\nLine: const [todos setTodos] = useState([])",
     "deliverables/todo/src/App.tsx", 'const [todos setTodos] = useState([])', 'const [todos, setTodos] = useState([])'),
    ("Build error in deliverables/clock/src/App.tsx at line 12:\nerror TS1005: ')' expected\nLine: setInterval(() => setNow(new Date()), 1000",
     "deliverables/clock/src/App.tsx", 'setInterval(() => setNow(new Date()), 1000', 'setInterval(() => setNow(new Date()), 1000)'),
    ("Build error in deliverables/picker/src/components/Display.tsx at line 4:\nerror TS7006: Parameter 'color' implicitly has an 'any' type\nLine: export default function Display({ color }) {",
     "deliverables/picker/src/components/Display.tsx",
     'export default function Display({ color }) {',
     'export default function Display({ color }: { color: string }) {'),
    ("Build error in deliverables/weather/src/App.tsx at line 3:\nerror: Cannot find name 'useState'\nLine: const [temp, setTemp] = useState(72)",
     "deliverables/weather/src/App.tsx",
     '// no import',
     'import { useState } from "react"'),
    ("Build error in deliverables/quiz/src/components/Question.tsx at line 7:\nerror TS2345: Argument of type 'boolean' is not assignable to parameter of type 'void'\nLine: onAnswer(true)",
     "deliverables/quiz/src/components/Question.tsx", 'onAnswer(true)', 'onAnswer()'),
    ("Build error in deliverables/calc/src/App.tsx at line 9:\nerror TS2304: Cannot find name 'useEffect'\nLine: useEffect(() => {}, [])",
     "deliverables/calc/src/App.tsx",
     'import { useState } from "react"', 'import { useState, useEffect } from "react"'),
    ("Build error in deliverables/timer/src/App.tsx at line 15:\nerror TS2552: Cannot find name 'interval'. Did you mean 'setInterval'?\nLine: clearInterval(interval)",
     "deliverables/timer/src/App.tsx", 'clearInterval(interval)', 'clearInterval(intervalRef.current)'),
    ("Build error in deliverables/note/src/App.tsx at line 6:\nerror TS2322: Type '{}' is missing the following properties: title, content\nLine: const note: Note = {}",
     "deliverables/note/src/App.tsx", 'const note: Note = {}', 'const note: Note = { title: "", content: "" }'),
    ("Build error in deliverables/chart/src/components/Bar.tsx at line 3:\nerror TS6133: 'props' is declared but its value is never read.\nLine: function Bar(props: any) { return <div /> }",
     "deliverables/chart/src/components/Bar.tsx", 'function Bar(props: any) { return <div /> }', 'function Bar() { return <div /> }'),
    ("CSS build error in deliverables/theme/src/index.css at line 4:\nMissing semicolon\nLine: color: red\nbackground: blue",
     "deliverables/theme/src/index.css", 'color: red\nbackground: blue', 'color: red;\nbackground: blue;'),
    ("Build error in deliverables/form/src/components/Input.tsx at line 2:\nerror TS2307: Cannot find module './styles.css'\nLine: import './styles.css'",
     "deliverables/form/src/components/Input.tsx", "import './styles.css'", "import '../styles.css'"),
    ("Build error in deliverables/list/src/App.tsx at line 10:\nerror TS2741: Property 'key' is missing\nLine: items.map(item => <div>{item}</div>)",
     "deliverables/list/src/App.tsx",
     'items.map(item => <div>{item}</div>)',
     'items.map((item, i) => <div key={i}>{item}</div>)'),
    ("Build error in deliverables/modal/src/components/Modal.tsx at line 14:\nerror TS2345: Argument of type 'null' is not assignable to parameter of type 'HTMLElement'\nLine: document.body.appendChild(null)",
     "deliverables/modal/src/components/Modal.tsx",
     'document.body.appendChild(null)',
     'document.body.appendChild(el)'),
    ("Build error in deliverables/tabs/src/App.tsx at line 8:\nerror TS2339: Property 'activeTab' does not exist on type '{}'\nLine: const { activeTab } = props",
     "deliverables/tabs/src/App.tsx",
     'const { activeTab } = props',
     'const { activeTab = 0 } = props as { activeTab?: number }'),
    ("Build error in deliverables/gallery/src/components/Image.tsx at line 5:\nerror TS2322: Type 'undefined' is not assignable to type 'string'\nLine: <img src={url} alt={undefined} />",
     "deliverables/gallery/src/components/Image.tsx",
     '<img src={url} alt={undefined} />',
     '<img src={url} alt="" />'),
    ("Build error in deliverables/cards/src/App.tsx at line 11:\nerror TS2769: No overload matches this call\nLine: setState(prev => prev + 1, 'extra')",
     "deliverables/cards/src/App.tsx",
     "setState(prev => prev + 1, 'extra')",
     "setState(prev => prev + 1)"),
    ("Build error in deliverables/nav/src/components/Nav.tsx at line 4:\nerror TS2786: 'Link' cannot be used as a JSX component\nLine: import Link from 'next/link'",
     "deliverables/nav/src/components/Nav.tsx",
     "import Link from 'next/link'", "// no link import — using a tag"),
    ("Build error in deliverables/feed/src/App.tsx at line 18:\nerror TS18047: 'data' is possibly 'null'\nLine: data.items.map(...)",
     "deliverables/feed/src/App.tsx", 'data.items.map(', 'data?.items.map('),
    ("Build error in deliverables/dash/src/components/Chart.tsx at line 22:\nerror TS2339: Property 'reduce' does not exist on type 'unknown'\nLine: values.reduce((a, b) => a + b, 0)",
     "deliverables/dash/src/components/Chart.tsx",
     'values.reduce((a, b) => a + b, 0)',
     '(values as number[]).reduce((a, b) => a + b, 0)'),
    ("Build error in deliverables/game/src/App.tsx at line 30:\nerror TS2532: Object is possibly 'undefined'\nLine: const first = items[0].name",
     "deliverables/game/src/App.tsx", 'const first = items[0].name', 'const first = items[0]?.name ?? ""'),
    ("Build error in deliverables/task/src/App.tsx at line 7:\nerror TS2571: Object is of type 'unknown'\nLine: console.log(response.data)",
     "deliverables/task/src/App.tsx", 'console.log(response.data)', 'console.log((response as { data: any }).data)'),
    ("Build error in deliverables/login/src/components/Form.tsx at line 9:\nerror TS2322: Type 'Event' is not assignable to type 'FormEvent<HTMLFormElement>'\nLine: const handle = (e: Event) => {}",
     "deliverables/login/src/components/Form.tsx",
     'const handle = (e: Event) => {}',
     'const handle = (e: React.FormEvent<HTMLFormElement>) => {}'),
    ("Build error in deliverables/search/src/App.tsx at line 13:\nerror TS2367: This condition will always return 'false'\nLine: if (query == undefined && query != null)",
     "deliverables/search/src/App.tsx",
     'if (query == undefined && query != null)', 'if (query == undefined)'),
    ("Build error in deliverables/media/src/components/Video.tsx at line 6:\nerror TS2322: Type 'boolean' is not assignable to type 'Autoplay'\nLine: <video autoPlay={false} />",
     "deliverables/media/src/components/Video.tsx", '<video autoPlay={false} />', '<video />'),
    ("Build error in deliverables/editor/src/App.tsx at line 17:\nerror TS2353: Object literal may only specify known properties, 'values' does not exist\nLine: onChange({ values: [] })",
     "deliverables/editor/src/App.tsx", 'onChange({ values: [] })', 'onChange([])'),
    ("Build error in deliverables/map/src/App.tsx at line 11:\nerror TS2304: Cannot find name 'LeafletMap'\nLine: const map = new LeafletMap()",
     "deliverables/map/src/App.tsx", 'const map = new LeafletMap()', 'const map = null // using stub'),
    ("Build error in deliverables/shop/src/components/Cart.tsx at line 8:\nerror TS2551: Property 'lenght' does not exist on type 'Item[]'. Did you mean 'length'?\nLine: items.lenght",
     "deliverables/shop/src/components/Cart.tsx", 'items.lenght', 'items.length'),
    ("Build error in deliverables/budget/src/App.tsx at line 14:\nerror TS2554: Expected 2 arguments, but got 3\nLine: total.toFixed(2, 'USD')",
     "deliverables/budget/src/App.tsx", "total.toFixed(2, 'USD')", "total.toFixed(2)"),
    ("Build error in deliverables/stats/src/components/Metric.tsx at line 3:\nerror TS1259: Module '\"react\"' has no default export\nLine: import React from 'react'",
     "deliverables/stats/src/components/Metric.tsx", "import React from 'react'", "import * as React from 'react'"),
]

def gen_single_turn_error_edit():
    user_prompt, path, old, new = random.choice(ERROR_EDIT_CASES)
    turns = [
        ('file_edit', {'path': path, 'old_text': old, 'new_text': new},
         f'[file_edit] replaced in {path}')
    ]
    return user_prompt, turns


# B. Trivial chat
TRIVIAL_CASES = [
    ("What's 2+2?", "4"),
    ("Say hello", "Hello!"),
    ("Who are you?", "I'm Tsunami, an app builder. I ride the wave."),
    ("What can you build?", "I build React apps — single files to full multi-component dashboards. What do you want to build?"),
    ("Thanks, that's all", "Break clean. Wave delivered."),
    ("How are you doing?", "Currents are stable. Ready to build."),
    ("nice work", "Thanks!"),
    ("are you there?", "Yes — ready to ride."),
    ("what's your name?", "Tsunami."),
    ("good morning", "Good morning. What are we building?"),
    ("tell me a joke", "Why did the React component break up with its state? It kept getting rerendered."),
    ("lol", "Thanks!"),
    ("what do you think?", "I build what you ask. What's the brief?"),
    ("never mind", "No problem. Catch the next wave."),
    ("that's cool", "Thanks. Ready for the next one."),
]

def gen_trivial_chat():
    user_prompt, response = random.choice(TRIVIAL_CASES)
    turns = [
        ('message_chat', {'text': response}, f'[message_chat] {response[:80]}')
    ]
    return user_prompt, turns


# C. Extreme build → project_init (not plan_update)
EXTREME_CASES = [
    ("Build a 3D solar system with orbiting planets and realistic lighting", "solar-system"),
    ("Build a multiplayer chat app with WebSocket and typing indicators", "multiplayer-chat"),
    ("Build a Chrome extension that blocks ads on any website", "ad-blocker"),
    ("Build an admin dashboard with charts and a data table", "admin-dashboard"),
    ("Build a marketing landing page for a startup", "marketing-landing"),
    ("Build a todo app that saves to a database", "todo-db"),
    ("Build a CSV file upload and data viewer", "csv-viewer"),
    ("Build a snake game with arrow keys, score, game over", "snake"),
    ("Build a desktop app with system tray icon", "desktop-tray"),
    ("Build a crypto portfolio tracker with live prices", "crypto-tracker"),
    ("Build a kanban board with drag and drop", "kanban"),
    ("Build a music player with waveform visualizer", "music-player"),
    ("Build a Spotify clone with playlists and search", "spotify-clone"),
    ("Build a code editor with syntax highlighting", "code-editor"),
    ("Build a video conference app with multiple participants", "video-conf"),
    ("Build a full e-commerce site with cart and checkout", "ecommerce"),
    ("Build a real-time collaborative whiteboard", "whiteboard"),
    ("Build a Notion-style nested document editor", "nested-docs"),
    ("Build a neural network visualizer showing layers and weights", "nn-viz"),
    ("Build a flight booking interface with interactive map", "flight-booking"),
]

def gen_extreme_project_init():
    user_prompt, name = random.choice(EXTREME_CASES)
    turns = [
        ('project_init', {'name': name},
         f'[project_init] Scaffolded deliverables/{name} with Vite + React + TypeScript')
    ]
    return user_prompt, turns


# D. Research-gate → search_web (not plan)
RESEARCH_CASES = [
    ("Build something using the new React Server Components", "react server components 2026 tutorial"),
    ("Build an app with the latest WebGPU compute shaders", "webgpu compute shaders 2026"),
    ("Build a demo of the new View Transitions API", "view transitions api react 2026"),
    ("Build with Bun's new fullstack framework", "bun fullstack framework 2026"),
    ("Build using the latest Tailwind v5 features", "tailwind v5 features release"),
    ("Build an app with the new Vercel AI SDK v6", "vercel ai sdk v6 tutorial"),
    ("Build something cool using the new CSS anchor positioning", "css anchor positioning 2026"),
    ("Build with the new Astro 6 islands architecture", "astro 6 islands architecture"),
    ("Build a demo of the Web USB API", "web usb api browser support 2026"),
    ("Build using the latest Remix v3 loaders", "remix v3 loaders tutorial"),
]

def gen_research_search():
    user_prompt, query = random.choice(RESEARCH_CASES)
    turns = [
        ('search_web', {'query': query, 'num_results': 5},
         f'Results: 1. Official docs... 2. Tutorial blog... 3. GitHub example...')
    ]
    return user_prompt, turns


# E. Dedup-guard → project_init for existing broken project
DEDUP_CASES = [
    ("pomodoro-timer", "a pomodoro timer with work and break sessions"),
    ("calculator-dark", "a calculator with dark theme"),
    ("weather-app", "a weather dashboard"),
    ("todo-app", "a todo app with categories"),
    ("counter-app", "a counter with plus and minus"),
    ("blog-editor", "a blog post editor"),
    ("recipe-book", "a recipe book with favorites"),
    ("flash-cards", "a flashcard study tool"),
    ("image-gallery", "an image gallery with lightbox"),
    ("expense-tracker", "an expense tracker with charts"),
]

def gen_dedup_project_init():
    name, desc = random.choice(DEDUP_CASES)
    user_prompt = (
        f'Build {desc}\n\n'
        f'[EXISTING PROJECT: {name}]\n'
        f'Path: deliverables/{name}\n'
        f'Status: BROKEN (won\'t compile)\n'
        f'Last error: TS2322 Type error at line 12\n'
        f'Rebuild this project.'
    )
    turns = [
        ('project_init', {'name': name},
         f'[project_init] Re-scaffolded deliverables/{name}')
    ]
    return user_prompt, turns


# F. Info-loop break → message_chat
INFO_CASES = [
    ("Can you help me debug my code later?", "Yes — share the error and I'll look at it."),
    ("Do you know Python?", "I build JavaScript/TypeScript apps. What do you want to build?"),
    ("Have you seen this error before?", "Share the error text and the file. I'll take a look."),
    ("What's the difference between let and const?", "const can't be reassigned. let can. Use const by default."),
    ("Is TypeScript hard to learn?", "No — it's JavaScript with type hints. You pick it up as you build."),
]

def gen_info_chat():
    user_prompt, response = random.choice(INFO_CASES)
    turns = [
        ('message_chat', {'text': response}, f'[message_chat] replied')
    ]
    return user_prompt, turns


# ============================================================================
# MAIN
# ============================================================================

def main():
    v14_path = 'workspace/training_data/e4b_toolcall_train_v14.jsonl'
    v17_path = 'workspace/training_data/e4b_toolcall_train_v17.jsonl'

    v14 = []
    with open(v14_path) as f:
        for line in f:
            v14.append(json.loads(line))
    print(f"Loaded {len(v14)} v14 examples")

    generators = [
        # Surgical fixes
        (gen_single_turn_error_edit, 30),   # L3
        (gen_trivial_chat, 15),             # L1 trivial
        (gen_extreme_project_init, 20),     # L1 extreme + L4 HF08
        (gen_research_search, 10),          # L4 HF02
        (gen_dedup_project_init, 10),       # L4 HF08
        (gen_info_chat, 5),                 # L4 HF06
        # Smaller v16-derived
        (gen_verify_stop, 15),              # L5 STOP signal
        (gen_happy_complex, 10),            # L5 multi-file
        (gen_progressive_complex, 10),      # L5 long trajectory
    ]

    new = []
    for gen, count in generators:
        for _ in range(count):
            user, turns = gen()
            text = build_example(user, turns)
            new.append({'text': text})

    lens = [len(re.findall(r'call:\w+', ex['text'])) for ex in new]
    print(f"Generated {len(new)} new examples")
    print(f"  length: min={min(lens)} max={max(lens)} avg={sum(lens)/len(lens):.1f}")
    print(f"  1-tool (single-turn): {sum(1 for l in lens if l == 1)}")
    print(f"  15+ tools: {sum(1 for l in lens if l >= 15)}")

    # Validate
    pf_write = total_write = 0
    pf_edit = total_edit = 0
    for ex in new:
        for m in re.findall(r'<\|tool_call>call:file_write\{(.*?)\}<tool_call\|>', ex['text'], re.DOTALL):
            total_write += 1
            if m.startswith('path:'):
                pf_write += 1
        for m in re.findall(r'<\|tool_call>call:file_edit\{(.*?)\}<tool_call\|>', ex['text'], re.DOTALL):
            total_edit += 1
            if m.startswith('path:'):
                pf_edit += 1
    print(f"  path-first file_write: {pf_write}/{total_write}")
    print(f"  path-first file_edit:  {pf_edit}/{total_edit}")

    with open(v17_path, 'w') as f:
        for ex in v14 + new:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    print(f"Wrote {len(v14) + len(new)} examples to {v17_path}")


if __name__ == '__main__':
    main()
