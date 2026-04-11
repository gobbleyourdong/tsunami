#!/usr/bin/env python3
"""v87 — v80 base + targeted examples for gaps + full tool coverage.

v80 (champion, 460): 19 examples, only 7/14 tools ever called.
Missing: search_web, file_read, match_glob, swell, swell_analyze,
         swell_build, message_info. Model flies on Gemma prior for these.

v87 strategy:
  - Keep all 19 v80 examples (proven baseline)
  - Add 1 extra bare L3 (ER01 npm install reinforcement)
  - Add 1 plan_update example (HF09)
  - Add 3 integration examples (L5 with components)
  - Add 5 tool-coverage examples (search_web, file_read, match_glob,
    swell_build, message_info) so all tools have at least 1 example

Total: 29 examples. Same hyperparams (epochs=10, grad_accum=4, lr=2e-4).

Also fixed: serve_transformers.py arg parser now handles booleans,
integers, and arrays (was silently dropping them).
"""
import json
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS, build_pipeline, build_messages
from build_v69 import APPS as APPS_V69
from build_v73 import build_l3_direct_fix, L3_EXAMPLES as V73_L3
from build_v78 import bare_l3, BARE_L3

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v87.jsonl"


# === NEW: Extra bare L3 for ER01 (npm install) ===
# v81r2 regressed on this: model retries build instead of npm install.
# Reinforce with a SECOND example using a different module name.
EXTRA_BARE_L3 = [
    dict(
        initial_cmd="cd deliverables/dashboard && npx vite build",
        error="Cannot find module 'chart.js'. You need to install it: npm install chart.js",
        fix_tool="shell_exec",
        fix_args={"command": "cd deliverables/dashboard && npm install chart.js"},
    ),
]


# === NEW: Plan gate example (HF09) ===
# User asks for complex build → model should plan_update FIRST, then pipeline.
def build_plan_example():
    """Full pipeline starting with plan_update for a complex build."""
    user_prompt = "I need a full e-commerce product page with image gallery, reviews section, size selector, and add-to-cart. Plan this carefully."
    turns = [
        ("plan_update", {
            "goal": "E-commerce product page with gallery, reviews, sizes, cart",
            "phases": [
                "Scaffold react-app project",
                "Write App.tsx with all sections: gallery, reviews, size selector, cart button",
                "Build and verify",
                "QA and deliver",
            ],
        }, "Plan created."),
        ("project_init", {"name": "product-page"}, "Created project deliverables/product-page"),
        ("file_write", {
            "path": "src/App.tsx",
            "content": (
                "import { useState } from 'react'\n"
                "import { Button, Card, Badge } from './components/ui'\n"
                "\n"
                "const SIZES = ['XS', 'S', 'M', 'L', 'XL']\n"
                "const IMAGES = ['/img/front.jpg', '/img/side.jpg', '/img/back.jpg']\n"
                "const REVIEWS = [\n"
                "  { user: 'Alex', rating: 5, text: 'Perfect fit!' },\n"
                "  { user: 'Sam', rating: 4, text: 'Good quality.' },\n"
                "]\n"
                "\n"
                "export default function App() {\n"
                "  const [size, setSize] = useState('M')\n"
                "  const [img, setImg] = useState(0)\n"
                "  return (\n"
                "    <div className='container p-6'>\n"
                "      <div className='grid grid-2 gap-6'>\n"
                "        <div>\n"
                "          <img src={IMAGES[img]} alt='product' className='rounded' style={{width:'100%'}} />\n"
                "          <div className='flex gap-2'>\n"
                "            {IMAGES.map((_, i) => <button key={i} onClick={() => setImg(i)} className={i===img?'badge':''}>{i+1}</button>)}\n"
                "          </div>\n"
                "        </div>\n"
                "        <div>\n"
                "          <h1>Premium Jacket</h1>\n"
                "          <Badge>In Stock</Badge>\n"
                "          <p className='text-muted'>$89.99</p>\n"
                "          <div className='flex gap-2'>\n"
                "            {SIZES.map(s => <Button key={s} onClick={() => setSize(s)} className={s===size?'bg-accent':''}>{s}</Button>)}\n"
                "          </div>\n"
                "          <Button className='bg-accent'>Add to Cart — {size}</Button>\n"
                "        </div>\n"
                "      </div>\n"
                "      <h2>Reviews</h2>\n"
                "      {REVIEWS.map((r, i) => <Card key={i}><strong>{r.user}</strong> {'★'.repeat(r.rating)} <p>{r.text}</p></Card>)}\n"
                "    </div>\n"
                "  )\n"
                "}\n"
            ),
        }, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/product-page && npx vite build"},
         "vite v5.0.0 building... built in 1.56s"),
        ("undertow", {"path": "deliverables/product-page/dist/index.html",
                      "expect": "product page with gallery, reviews, sizes, cart"},
         "Screenshot taken. App renders correctly: gallery, reviews, size buttons, cart."),
        ("message_result", {"text": "Built product-page: e-commerce product page with image gallery, reviews, size selector, and add-to-cart. Ready in deliverables/product-page."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


# === NEW: Integration examples (L5-targeted) ===
# Full pipeline with component imports, showing the model how to build
# multi-component apps end-to-end.

INTEGRATION_APPS = [
    # Medium: todo app with Card and Button components
    ("todo-components", "a todo app with cards for each item", [
        ("src/App.tsx", (
            "import { useState } from 'react'\n"
            "import { Button, Card, Input } from './components/ui'\n"
            "\n"
            "export default function App() {\n"
            "  const [todos, setTodos] = useState<{text: string, done: boolean}[]>([])\n"
            "  const [input, setInput] = useState('')\n"
            "  const add = () => { if (input.trim()) { setTodos([...todos, {text: input, done: false}]); setInput('') } }\n"
            "  const toggle = (i: number) => setTodos(todos.map((t, j) => j === i ? {...t, done: !t.done} : t))\n"
            "  const remove = (i: number) => setTodos(todos.filter((_, j) => j !== i))\n"
            "  return (\n"
            "    <div className='container p-6'>\n"
            "      <h1>Todo List</h1>\n"
            "      <div className='flex gap-2'>\n"
            "        <Input value={input} onChange={(e: any) => setInput(e.target.value)} placeholder='Add task...' />\n"
            "        <Button onClick={add}>Add</Button>\n"
            "      </div>\n"
            "      <div className='flex-col gap-2' style={{marginTop: '1rem'}}>\n"
            "        {todos.map((t, i) => (\n"
            "          <Card key={i} className={t.done ? 'text-muted' : ''}>\n"
            "            <div className='flex' style={{justifyContent: 'space-between', alignItems: 'center'}}>\n"
            "              <span onClick={() => toggle(i)} style={{cursor: 'pointer', textDecoration: t.done ? 'line-through' : 'none'}}>{t.text}</span>\n"
            "              <Button onClick={() => remove(i)}>✕</Button>\n"
            "            </div>\n"
            "          </Card>\n"
            "        ))}\n"
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )),
    ]),
    # Medium: timer with Progress component
    ("focus-timer", "a focus timer with progress ring", [
        ("src/App.tsx", (
            "import { useState, useEffect } from 'react'\n"
            "import { Button, Card, Progress } from './components/ui'\n"
            "\n"
            "export default function App() {\n"
            "  const TOTAL = 25 * 60\n"
            "  const [secs, setSecs] = useState(TOTAL)\n"
            "  const [running, setRunning] = useState(false)\n"
            "  useEffect(() => {\n"
            "    if (!running || secs <= 0) return\n"
            "    const id = setInterval(() => setSecs(s => s - 1), 1000)\n"
            "    return () => clearInterval(id)\n"
            "  }, [running, secs])\n"
            "  const pct = ((TOTAL - secs) / TOTAL) * 100\n"
            "  const mm = String(Math.floor(secs / 60)).padStart(2, '0')\n"
            "  const ss = String(secs % 60).padStart(2, '0')\n"
            "  return (\n"
            "    <div className='container p-6 flex-col flex-center'>\n"
            "      <Card className='p-6 text-center'>\n"
            "        <h1 style={{fontSize: '3rem'}}>{mm}:{ss}</h1>\n"
            "        <Progress value={pct} />\n"
            "        <div className='flex gap-2' style={{marginTop: '1rem', justifyContent: 'center'}}>\n"
            "          <Button onClick={() => setRunning(!running)}>{running ? 'Pause' : 'Start'}</Button>\n"
            "          <Button onClick={() => { setRunning(false); setSecs(TOTAL) }}>Reset</Button>\n"
            "        </div>\n"
            "      </Card>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )),
    ]),
    # Hard: expense tracker WITH error recovery cycle
    ("expense-tracker", "an expense tracker with categories and totals", [
        ("src/App.tsx", (
            "import { useState } from 'react'\n"
            "import { Button, Card, Input, Badge, Select } from './components/ui'\n"
            "\n"
            "const CATEGORIES = ['Food', 'Transport', 'Entertainment', 'Bills', 'Other']\n"
            "\n"
            "type Expense = { desc: string; amount: number; category: string }\n"
            "\n"
            "export default function App() {\n"
            "  const [expenses, setExpenses] = useState<Expense[]>([])\n"
            "  const [desc, setDesc] = useState('')\n"
            "  const [amount, setAmount] = useState('')\n"
            "  const [cat, setCat] = useState('Food')\n"
            "  const add = () => {\n"
            "    if (desc && amount) {\n"
            "      setExpenses([...expenses, { desc, amount: parseFloat(amount), category: cat }])\n"
            "      setDesc(''); setAmount('')\n"
            "    }\n"
            "  }\n"
            "  const total = expenses.reduce((s, e) => s + e.amount, 0)\n"
            "  const byCategory = CATEGORIES.map(c => ({\n"
            "    name: c,\n"
            "    total: expenses.filter(e => e.category === c).reduce((s, e) => s + e.amount, 0),\n"
            "  })).filter(c => c.total > 0)\n"
            "  return (\n"
            "    <div className='container p-6'>\n"
            "      <h1>Expense Tracker</h1>\n"
            "      <Card className='p-4'>\n"
            "        <div className='flex gap-2'>\n"
            "          <Input value={desc} onChange={(e: any) => setDesc(e.target.value)} placeholder='Description' />\n"
            "          <Input type='number' value={amount} onChange={(e: any) => setAmount(e.target.value)} placeholder='Amount' />\n"
            "          <Select value={cat} onChange={(e: any) => setCat(e.target.value)}>\n"
            "            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}\n"
            "          </Select>\n"
            "          <Button onClick={add}>Add</Button>\n"
            "        </div>\n"
            "      </Card>\n"
            "      <div className='grid grid-2 gap-4' style={{marginTop: '1rem'}}>\n"
            "        <Card className='p-4'>\n"
            "          <h2>Expenses</h2>\n"
            "          {expenses.map((e, i) => (\n"
            "            <div key={i} className='flex' style={{justifyContent: 'space-between', padding: '0.25rem 0'}}>\n"
            "              <span>{e.desc} <Badge>{e.category}</Badge></span>\n"
            "              <strong>${e.amount.toFixed(2)}</strong>\n"
            "            </div>\n"
            "          ))}\n"
            "          <div className='divider' />\n"
            "          <div className='flex' style={{justifyContent: 'space-between'}}>\n"
            "            <strong>Total</strong><strong>${total.toFixed(2)}</strong>\n"
            "          </div>\n"
            "        </Card>\n"
            "        <Card className='p-4'>\n"
            "          <h2>By Category</h2>\n"
            "          {byCategory.map(c => (\n"
            "            <div key={c.name} className='flex' style={{justifyContent: 'space-between', padding: '0.25rem 0'}}>\n"
            "              <span>{c.name}</span><strong>${c.total.toFixed(2)}</strong>\n"
            "            </div>\n"
            "          ))}\n"
            "        </Card>\n"
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )),
    ]),
]


def build_integration_with_error(name, desc, files):
    """Build an integration example with a build error + fix cycle.

    Shows: project_init → file_write → shell_exec (ERROR) → file_edit (FIX) →
           shell_exec (SUCCESS) → undertow → message_result
    """
    user_prompt = f"Build me {desc}."
    turns = []
    turns.append(("project_init", {"name": name}, f"Created project deliverables/{name}"))
    for path, content in files:
        # Use relative path (consistent with build_pipeline convention)
        turns.append(("file_write", {"path": path, "content": content}, f"Wrote {path}"))

    # First build fails (missing type annotation — realistic error)
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "Error: src/App.tsx(7,45): Argument of type 'string' is not assignable to parameter of type 'number'."))
    # Fix the error with file_edit (full path, consistent with L3 convention)
    turns.append(("file_edit", {
        "path": f"deliverables/{name}/src/App.tsx",
        "old_text": "parseFloat(amount)",
        "new_text": "Number(amount) || 0",
    }, "OK"))
    # Rebuild succeeds
    turns.append(("shell_exec", {"command": f"cd deliverables/{name} && npx vite build"},
                  "vite v5.0.0 building for production... built in 1.89s"))
    turns.append(("undertow", {"path": f"deliverables/{name}/dist/index.html", "expect": desc},
                  "Screenshot taken. App renders correctly."))
    turns.append(("message_result", {"text": f"Built {name}: {desc}. Ready in deliverables/{name}."},
                  "Delivered."))
    return build_messages(user_prompt, turns)


# === NEW: Tool-coverage examples ===
# Every tool in the schema should appear at least once in training data.

def build_search_then_build():
    """Visual clone: search_web → project_init → pipeline (HF02 pattern)."""
    user_prompt = "Build a page that looks like the Stripe pricing page."
    turns = [
        ("search_web", {"query": "Stripe pricing page layout 2026"},
         "Results: 1. stripe.com/pricing — 3-tier cards, toggle monthly/annual, feature comparison table."),
        ("project_init", {"name": "pricing-clone"}, "Created project deliverables/pricing-clone"),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import { useState } from 'react'\n"
            "import { Button, Card, Badge } from './components/ui'\n"
            "\n"
            "const PLANS = [\n"
            "  { name: 'Starter', price: 0, features: ['100 requests/mo', 'Community support'] },\n"
            "  { name: 'Pro', price: 25, features: ['10K requests/mo', 'Email support', 'Analytics'] },\n"
            "  { name: 'Enterprise', price: 99, features: ['Unlimited', 'Priority support', 'SLA'] },\n"
            "]\n"
            "\n"
            "export default function App() {\n"
            "  const [annual, setAnnual] = useState(false)\n"
            "  return (\n"
            "    <div className='container p-6 text-center'>\n"
            "      <h1>Pricing</h1>\n"
            "      <Button onClick={() => setAnnual(!annual)}>{annual ? 'Annual' : 'Monthly'}</Button>\n"
            "      <div className='grid grid-3 gap-4' style={{marginTop:'2rem'}}>\n"
            "        {PLANS.map(p => (\n"
            "          <Card key={p.name} className='p-4'>\n"
            "            <h2>{p.name}</h2>\n"
            "            <p style={{fontSize:'2rem'}}>${annual ? p.price*10 : p.price}/mo</p>\n"
            "            {p.features.map(f => <p key={f}>{f}</p>)}\n"
            "            <Button>Get Started</Button>\n"
            "          </Card>\n"
            "        ))}\n"
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/pricing-clone && npx vite build"},
         "vite v5.0.0 building... built in 1.12s"),
        ("undertow", {"path": "deliverables/pricing-clone/dist/index.html",
                      "expect": "pricing page with 3 tiers"}, "Verified."),
        ("message_result", {"text": "Built pricing-clone: Stripe-style pricing page. Ready."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def build_read_then_edit():
    """Modify existing project: file_read → file_edit (L5 error recovery pattern)."""
    user_prompt = "The todo app is missing a clear-all button. Add one."
    turns = [
        ("file_read", {"path": "deliverables/todo/src/App.tsx"},
         "import { useState } from 'react'\n\nexport default function App() {\n  const [todos, setTodos] = useState<string[]>([])\n  const [v, setV] = useState('')\n  return (\n    <div>\n      <input value={v} onChange={e => setV(e.target.value)} />\n      <button onClick={() => { if (v) { setTodos([...todos, v]); setV('') } }}>Add</button>\n      <ul>{todos.map((t, i) => <li key={i}>{t}</li>)}</ul>\n    </div>\n  )\n}"),
        ("file_edit", {
            "path": "deliverables/todo/src/App.tsx",
            "old_text": "      <ul>{todos.map((t, i) => <li key={i}>{t}</li>)}</ul>",
            "new_text": "      <button onClick={() => setTodos([])}>Clear All</button>\n      <ul>{todos.map((t, i) => <li key={i}>{t}</li>)}</ul>",
        }, "OK"),
        ("shell_exec", {"command": "cd deliverables/todo && npx vite build"},
         "vite v5.0.0 building... built in 0.98s"),
        ("message_result", {"text": "Added clear-all button to todo app."}, "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def build_glob_then_read():
    """Explore project: match_glob → file_read (project discovery pattern)."""
    user_prompt = "What components does the dashboard project have?"
    turns = [
        ("match_glob", {"pattern": "deliverables/dashboard/src/**/*.tsx"},
         "deliverables/dashboard/src/App.tsx\ndeliverables/dashboard/src/components/Sidebar.tsx\ndeliverables/dashboard/src/components/StatCard.tsx\ndeliverables/dashboard/src/components/DataTable.tsx"),
        ("file_read", {"path": "deliverables/dashboard/src/App.tsx"},
         "import Sidebar from './components/Sidebar'\nimport StatCard from './components/StatCard'\nimport DataTable from './components/DataTable'\n\nexport default function App() { return <div className='flex'><Sidebar /><div><StatCard /><DataTable /></div></div> }"),
        ("message_result", {"text": "Dashboard has 4 components: App.tsx (layout), Sidebar, StatCard, DataTable. App imports all three."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def build_swell_example():
    """Parallel build: swell_build for multi-component app."""
    user_prompt = "Build a dashboard with sidebar, stats cards, and data table."
    turns = [
        ("project_init", {"name": "analytics-dash"}, "Created project deliverables/analytics-dash"),
        ("swell_build", {"components": [
            {"path": "deliverables/analytics-dash/src/components/Sidebar.tsx",
             "spec": "Navigation sidebar with links: Dashboard, Analytics, Settings"},
            {"path": "deliverables/analytics-dash/src/components/StatCards.tsx",
             "spec": "Row of 4 stat cards: Users, Revenue, Orders, Conversion"},
            {"path": "deliverables/analytics-dash/src/components/DataTable.tsx",
             "spec": "Sortable table with sample data rows"},
        ]}, "Dispatched 3 eddies. All components written."),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import Sidebar from './components/Sidebar'\n"
            "import StatCards from './components/StatCards'\n"
            "import DataTable from './components/DataTable'\n"
            "\n"
            "export default function App() {\n"
            "  return (\n"
            "    <div className='flex'>\n"
            "      <Sidebar />\n"
            "      <div className='container p-6'>\n"
            "        <h1>Analytics Dashboard</h1>\n"
            "        <StatCards />\n"
            "        <DataTable />\n"
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/analytics-dash && npx vite build"},
         "vite v5.0.0 building... built in 1.45s"),
        ("undertow", {"path": "deliverables/analytics-dash/dist/index.html",
                      "expect": "dashboard with sidebar, stats, table"}, "Verified."),
        ("message_result", {"text": "Built analytics-dash: dashboard with sidebar, stat cards, data table."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def build_message_info_example():
    """Status update: message_info during work, message_result to deliver."""
    user_prompt = "Build a weather app. Let me know your progress."
    turns = [
        ("message_info", {"text": "Starting weather app. Scaffolding first."}, "OK"),
        ("project_init", {"name": "weather-app"}, "Created project deliverables/weather-app"),
        ("file_write", {"path": "src/App.tsx", "content": (
            "import { useState } from 'react'\n"
            "import { Card, Button, Input } from './components/ui'\n"
            "\n"
            "export default function App() {\n"
            "  const [city, setCity] = useState('Tokyo')\n"
            "  const [weather] = useState({ temp: 22, desc: 'Sunny', humidity: 45 })\n"
            "  return (\n"
            "    <div className='container p-6 flex-col flex-center'>\n"
            "      <Card className='p-6'>\n"
            "        <div className='flex gap-2'>\n"
            "          <Input value={city} onChange={(e: any) => setCity(e.target.value)} />\n"
            "          <Button>Search</Button>\n"
            "        </div>\n"
            "        <h1>{city}</h1>\n"
            "        <p style={{fontSize:'3rem'}}>{weather.temp}°C</p>\n"
            "        <p className='text-muted'>{weather.desc} — {weather.humidity}% humidity</p>\n"
            "      </Card>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )}, "Wrote App.tsx"),
        ("shell_exec", {"command": "cd deliverables/weather-app && npx vite build"},
         "vite v5.0.0 building... built in 1.01s"),
        ("undertow", {"path": "deliverables/weather-app/dist/index.html",
                      "expect": "weather app with city search"}, "Verified."),
        ("message_result", {"text": "Built weather-app: weather display with city search. Ready in deliverables/weather-app."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def build_swell_generic():
    """Generic parallel dispatch: swell for multi-task work."""
    user_prompt = "Set up the project: install dependencies, create a .env file, and run the linter."
    turns = [
        ("swell", {"tasks": [
            "shell_exec: cd deliverables/app && npm install",
            "file_write: deliverables/app/.env with VITE_API_URL=http://localhost:3000",
            "shell_exec: cd deliverables/app && npx eslint src/",
        ]}, "3 eddies dispatched. All tasks complete: deps installed, .env created, lint clean."),
        ("message_result", {"text": "Project setup complete: deps installed, .env configured, linter passed."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def build_swell_analyze_example():
    """Parallel analysis: swell_analyze to read multiple dirs."""
    user_prompt = "Compare the counter and todo projects — which has more components?"
    turns = [
        ("swell_analyze", {
            "paths": ["deliverables/counter/src/", "deliverables/todo/src/"],
            "question": "How many .tsx component files exist and what are they?",
        }, "counter: 1 file (App.tsx). todo: 3 files (App.tsx, TodoItem.tsx, TodoList.tsx)."),
        ("message_result", {"text": "Todo has more components (3 vs 1). Counter is just App.tsx, while todo has App.tsx + TodoItem + TodoList."},
         "Delivered."),
    ]
    return build_messages(user_prompt, turns)


def main():
    print(f"Loading: {MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)

    # Verify SYSTEM_TEXT has all required content
    assert "Components" in SYSTEM_TEXT, "Missing component guide"
    assert "CSS resolution" in SYSTEM_TEXT or "reef" in SYSTEM_TEXT, "Missing error recovery rules"
    assert "NEVER message_chat" in SYSTEM_TEXT, "Missing path fix trigger"
    assert "Visual clones" in SYSTEM_TEXT, "Missing visual clone trigger"
    assert "plan" in SYSTEM_TEXT.lower(), "Missing plan trigger"
    print("SYSTEM_TEXT verified.")

    examples = []

    # === BASELINE: 19 v80 examples (proven) ===

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

    # 3. Bare-format L3: 3 (from v78)
    for sc in BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # === NEW: +5 targeted examples ===

    # 4. Extra bare L3: 1 (reinforce npm install for ER01 regression)
    for sc in EXTRA_BARE_L3:
        msgs = bare_l3(sc["initial_cmd"], sc["error"], sc["fix_tool"], sc["fix_args"])
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # 5. Plan gate: 1 (HF09 — complex build → plan_update FIRST)
    msgs = build_plan_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 6. Integration: 2 happy + 1 with error recovery (L5-targeted)
    for name, desc, files in INTEGRATION_APPS[:2]:
        msgs = build_pipeline(name, desc, files, parallel=False)
        text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        examples.append({"text": text})

    # The expense tracker gets the error recovery variant
    name, desc, files = INTEGRATION_APPS[2]
    msgs = build_integration_with_error(name, desc, files)
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # === NEW: +5 tool-coverage examples ===

    # 7. search_web: visual clone (HF02 pattern)
    msgs = build_search_then_build()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 8. file_read → file_edit: modify existing project
    msgs = build_read_then_edit()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 9. match_glob → file_read: project exploration
    msgs = build_glob_then_read()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 10. swell_build: parallel multi-component build
    msgs = build_swell_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 11. message_info: status updates during build
    msgs = build_message_info_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 12. swell: generic parallel dispatch
    msgs = build_swell_generic()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # 13. swell_analyze: parallel file analysis
    msgs = build_swell_analyze_example()
    text = tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    examples.append({"text": text})

    # === Summary ===
    print(f"\nTotal: {len(examples)} examples")
    print(f"  10 happy path (v69)")
    print(f"  6 pipeline L3 (v73)")
    print(f"  3 bare L3 (v78)")
    print(f"  1 extra bare L3 (ER01 reinforce)")
    print(f"  1 plan gate (HF09)")
    print(f"  2 integration happy (L5 with components)")
    print(f"  1 integration + error recovery (L5 expense tracker)")
    print(f"  7 tool coverage (ALL 14 tools now represented)")

    starts_bos = sum(1 for ex in examples if ex["text"].startswith("<bos>"))
    print(f"Starts with <bos>: {starts_bos}/{len(examples)}")

    # Verify triggers in rendered text
    checks = {
        "Components": sum(1 for ex in examples if "components/ui" in ex["text"]),
        "CSS resolution": sum(1 for ex in examples if "CSS resolution" in ex["text"]),
        "npm install": sum(1 for ex in examples if "npm install" in ex["text"]),
        "plan_update": sum(1 for ex in examples if "plan_update" in ex["text"]),
    }
    for k, v in checks.items():
        print(f"  '{k}' in examples: {v}/{len(examples)}")

    os.makedirs(os.path.dirname(OUT_PATH) if os.path.dirname(OUT_PATH) else ".", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\nWrote {len(examples)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
