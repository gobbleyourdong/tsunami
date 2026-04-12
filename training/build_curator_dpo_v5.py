#!/usr/bin/env python3
"""build_curator_dpo_v5.py — Fire 21 (Builder DPO v5)

Targeting L3 error recovery failures from eval_report_v9:
  ER02 (3 pairs): Type error in build output → file_edit directly (not file_read)
  ER03 (3 pairs): Syntax error in build output → file_edit directly (not file_read)
  ER06 (3 pairs): Unresolved import → file_edit to remove/fix import (not file_read)
  ER05 (3 pairs): Wrong cd path → shell_exec with correct deliverables/appname path

Total: 12 new DPO pairs
"""
from __future__ import annotations
import json, datetime
from pathlib import Path
from transformers import AutoTokenizer

MODEL_ID = "google/gemma-4-e4b-it"
OUT_DIR  = Path("workspace/training_data")
OUT_FILE = OUT_DIR / "curator_dpo_v5.jsonl"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading tokenizer...")
tok = AutoTokenizer.from_pretrained(MODEL_ID)
print("Tokenizer loaded.")

TODAY = datetime.date.today().isoformat()

SYSTEM = """You are Tsunami. You build apps by calling tools.

Pipeline: project_init → file_write(App.tsx) → shell_exec(npm run build) → fix if needed → undertow → message_result

Error recovery rules:
- When a build error contains a specific line/column number and code snippet, DIRECTLY file_edit to fix it — do NOT file_read first.
- The error message tells you exactly what to change. Trust it.
- Type errors: change the wrong type to the right type at the line specified.
- Syntax errors: fix the missing bracket/paren/brace at the line specified.
- Unresolved import: remove or correct the import at the top of the file.
- Wrong path (cd fails): re-run with the correct deliverables/appname path.
- After 2 identical shell failures: file_write a replacement, not file_read.

One tool call per response.
"""

TOOLS = [
    {"type": "function", "function": {"name": "project_init",  "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write",    "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit",     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "file_read",     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "shell_exec",    "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "undertow",      "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_result","parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat",  "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web",    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update",   "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
]

def tokenize_chat(msgs: list[dict]) -> str:
    return tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False, add_generation_prompt=True)

def make_pair(
    prompt_msgs: list[dict],
    chosen_fn: str, chosen_args: dict,
    rejected_fn: str, rejected_args: dict,
    source_bug: str,
    note: str,
) -> dict:
    prompt_text = tokenize_chat(prompt_msgs)
    chosen_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "c_ch", "type": "function", "function": {"name": chosen_fn, "arguments": json.dumps(chosen_args)}}
    ]}]
    rejected_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "c_rj", "type": "function", "function": {"name": rejected_fn, "arguments": json.dumps(rejected_args)}}
    ]}]
    chosen_text  = tok.apply_chat_template(prompt_msgs + chosen_msg,  tools=TOOLS, tokenize=False)
    rejected_text = tok.apply_chat_template(prompt_msgs + rejected_msg, tools=TOOLS, tokenize=False)
    return {
        "prompt":      prompt_text,
        "chosen":      chosen_text[len(prompt_text):],
        "rejected":    rejected_text[len(prompt_text):],
        "source_bug":  source_bug,
        "note":        note,
        "images":      [],
        "date":        TODAY,
    }

def tc(tool_name, **kw):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": f"ev_{tool_name}", "type": "function", "function": {"name": tool_name, "arguments": json.dumps(kw)}}
    ]}

def tr(name, content):
    return {"role": "tool", "tool_call_id": f"ev_{name}", "name": name, "content": content}


PAIRS = []

# ══════════════════════════════════════════════════════════════════
# ER02: Type error — direct file_edit, not file_read
# ══════════════════════════════════════════════════════════════════

# ER02a: setError(null) should be setError('')
ER02A_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a search app with an error state."},
    tc("project_init", name="search-app"),
    tr("project_init", "Scaffolded 'search-app'. Write src/App.tsx."),
    tc("file_write", path="src/App.tsx", content="const [error, setError] = useState<string>('');"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/search-app && npm run build"),
    tr("shell_exec", "[shell_exec] Error: src/App.tsx(12,5): Type 'null' is not assignable to type 'string'. setError(null) should be setError('')"),
]
PAIRS.append(make_pair(ER02A_MSGS,
    chosen_fn="file_edit",
    chosen_args={"path": "src/App.tsx", "old_text": "setError(null)", "new_text": "setError('')"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER02-type-error",
    note="er02a: Type 'null' not assignable to 'string' → file_edit setError(null)→setError(''); not file_read",
))

# ER02b: undefined assigned to number
ER02B_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a budget tracker."},
    tc("project_init", name="budget-tracker"),
    tr("project_init", "Scaffolded."),
    tc("file_write", path="src/App.tsx", content="let total: number = undefined;"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/budget-tracker && npm run build"),
    tr("shell_exec", "[shell_exec] Error: src/App.tsx(8,7): Type 'undefined' is not assignable to type 'number'. Replace undefined with 0."),
]
PAIRS.append(make_pair(ER02B_MSGS,
    chosen_fn="file_edit",
    chosen_args={"path": "src/App.tsx", "old_text": "let total: number = undefined;", "new_text": "let total: number = 0;"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER02-type-error",
    note="er02b: Type 'undefined' not assignable to 'number' → file_edit undefined→0; not file_read",
))

# ER02c: string passed to number prop
ER02C_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a data table component."},
    tc("project_init", name="data-table"),
    tr("project_init", "Scaffolded."),
    tc("file_write", path="src/App.tsx", content='<Table rowCount="5" />'),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/data-table && npm run build"),
    tr("shell_exec", "[shell_exec] Error: src/App.tsx(15,20): Type 'string' is not assignable to type 'number'. rowCount expects a number, not a string literal."),
]
PAIRS.append(make_pair(ER02C_MSGS,
    chosen_fn="file_edit",
    chosen_args={"path": "src/App.tsx", "old_text": 'rowCount="5"', "new_text": "rowCount={5}"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER02-type-error",
    note="er02c: Type 'string' not assignable to 'number' for rowCount → file_edit string→number literal; not file_read",
))

# ══════════════════════════════════════════════════════════════════
# ER03: Syntax error — direct file_edit, not file_read
# ══════════════════════════════════════════════════════════════════

# ER03a: missing closing paren in .map()
ER03A_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a todo list app."},
    tc("project_init", name="todo-list"),
    tr("project_init", "Scaffolded."),
    tc("file_write", path="src/App.tsx", content="{items.map(i => <div key={i}>{i}</div>}"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/todo-list && npm run build"),
    tr("shell_exec", "[shell_exec] Error: src/App.tsx(8,45): Expected ')' to close '(' at line 8. {items.map(i => <div key={i}>{i}</div>"),
]
PAIRS.append(make_pair(ER03A_MSGS,
    chosen_fn="file_edit",
    chosen_args={"path": "src/App.tsx", "old_text": "{items.map(i => <div key={i}>{i}</div>}", "new_text": "{items.map(i => <div key={i}>{i}</div>)}"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER03-syntax-error",
    note="er03a: Missing ')' in .map() → file_edit to add closing paren; not file_read",
))

# ER03b: unclosed JSX tag
ER03B_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a card component app."},
    tc("project_init", name="card-app"),
    tr("project_init", "Scaffolded."),
    tc("file_write", path="src/App.tsx", content="<div className='card'><h2>{title}</h2><p>{desc}</p>"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/card-app && npm run build"),
    tr("shell_exec", "[shell_exec] Error: src/App.tsx(6,52): JSX element 'div' has no corresponding closing tag. Add </div> to close the opening tag."),
]
PAIRS.append(make_pair(ER03B_MSGS,
    chosen_fn="file_edit",
    chosen_args={"path": "src/App.tsx", "old_text": "<div className='card'><h2>{title}</h2><p>{desc}</p>", "new_text": "<div className='card'><h2>{title}</h2><p>{desc}</p></div>"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER03-syntax-error",
    note="er03b: Unclosed JSX <div> → file_edit to add </div>; not file_read",
))

# ER03c: missing closing brace in object
ER03C_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build an expense tracker."},
    tc("project_init", name="expense-tracker"),
    tr("project_init", "Scaffolded."),
    tc("file_write", path="src/App.tsx", content="const config = { theme: 'dark', currency: 'USD'"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/expense-tracker && npm run build"),
    tr("shell_exec", "[shell_exec] Error: src/App.tsx(4,48): '}' expected. The object literal 'config' is missing its closing brace."),
]
PAIRS.append(make_pair(ER03C_MSGS,
    chosen_fn="file_edit",
    chosen_args={"path": "src/App.tsx", "old_text": "const config = { theme: 'dark', currency: 'USD'", "new_text": "const config = { theme: 'dark', currency: 'USD' }"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER03-syntax-error",
    note="er03c: Missing closing } in config object → file_edit to add }; not file_read",
))

# ══════════════════════════════════════════════════════════════════
# ER06: Unresolved import — file_edit to remove/fix, not file_read
# ══════════════════════════════════════════════════════════════════

# ER06a: leaflet CSS import missing
ER06A_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a map viewer app."},
    tc("project_init", name="map-viewer"),
    tr("project_init", "Scaffolded."),
    tc("file_write", path="src/App.tsx", content="import 'leaflet/dist/leaflet.css';\nimport L from 'leaflet';"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/map-viewer && npm run build"),
    tr("shell_exec", "[shell_exec] Error: Could not resolve 'leaflet/dist/leaflet.css' from src/App.tsx. Install leaflet with npm or remove the import."),
]
PAIRS.append(make_pair(ER06A_MSGS,
    chosen_fn="file_edit",
    chosen_args={"path": "src/App.tsx", "old_text": "import 'leaflet/dist/leaflet.css';\nimport L from 'leaflet';", "new_text": "import L from 'leaflet';"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER06-unresolved-import",
    note="er06a: leaflet CSS not found → file_edit to remove CSS import; not file_read",
))

# ER06b: missing local component import
ER06B_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a dashboard with a header component."},
    tc("project_init", name="dashboard-app"),
    tr("project_init", "Scaffolded."),
    tc("file_write", path="src/App.tsx", content="import Header from './components/Header';\nexport default function App() { return <Header /> }"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/dashboard-app && npm run build"),
    tr("shell_exec", "[shell_exec] Error: Could not resolve './components/Header' from src/App.tsx. File does not exist at src/components/Header.tsx"),
]
PAIRS.append(make_pair(ER06B_MSGS,
    chosen_fn="file_write",
    chosen_args={"path": "src/components/Header.tsx", "content": "export default function Header() { return <header className='p-4 bg-gray-900 text-white'><h1>Dashboard</h1></header> }"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER06-unresolved-import",
    note="er06b: Missing Header component → file_write to create it; not file_read of App.tsx",
))

# ER06c: wrong package name in import
ER06C_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a chart app with recharts."},
    tc("project_init", name="chart-app"),
    tr("project_init", "Scaffolded."),
    tc("file_write", path="src/App.tsx", content="import { BarChart } from 'react-charts';"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/chart-app && npm run build"),
    tr("shell_exec", "[shell_exec] Error: Could not resolve 'react-charts' from src/App.tsx. Did you mean 'recharts'? Update the import statement."),
]
PAIRS.append(make_pair(ER06C_MSGS,
    chosen_fn="file_edit",
    chosen_args={"path": "src/App.tsx", "old_text": "import { BarChart } from 'react-charts';", "new_text": "import { BarChart, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER06-unresolved-import",
    note="er06c: Wrong package 'react-charts' → file_edit to 'recharts'; not file_read",
))

# ══════════════════════════════════════════════════════════════════
# ER05: Wrong path — re-run shell with correct deliverables/appname path
# ══════════════════════════════════════════════════════════════════

# ER05a: cd app instead of cd deliverables/app
ER05A_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a weather dashboard."},
    tc("project_init", name="weather-dashboard"),
    tr("project_init", "Scaffolded 'weather-dashboard' in deliverables/weather-dashboard."),
    tc("file_write", path="src/App.tsx", content="export default function App() { return <div>Weather</div> }"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd weather-dashboard && npm run build"),
    tr("shell_exec", "[shell_exec] Error: No such file or directory: weather-dashboard. Projects are in deliverables/. Try: cd deliverables/weather-dashboard && npm run build"),
]
PAIRS.append(make_pair(ER05A_MSGS,
    chosen_fn="shell_exec",
    chosen_args={"command": "cd deliverables/weather-dashboard && npm run build"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER05-wrong-path",
    note="er05a: Wrong cd path (missing deliverables/) → shell_exec with correct path; not file_read",
))

# ER05b: absolute path instead of relative deliverables/
ER05B_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a kanban board."},
    tc("project_init", name="kanban-board"),
    tr("project_init", "Scaffolded 'kanban-board' in deliverables/kanban-board."),
    tc("file_write", path="src/App.tsx", content="export default function App() { return <div>Kanban</div> }"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd /workspace/kanban-board && npm run build"),
    tr("shell_exec", "[shell_exec] Error: No such file or directory: /workspace/kanban-board. Use relative path: cd deliverables/kanban-board && npm run build"),
]
PAIRS.append(make_pair(ER05B_MSGS,
    chosen_fn="shell_exec",
    chosen_args={"command": "cd deliverables/kanban-board && npm run build"},
    rejected_fn="shell_exec",
    rejected_args={"command": "cd /workspace/kanban-board && npm run build"},
    source_bug="ER05-wrong-path",
    note="er05b: Absolute path failed → shell_exec with correct relative deliverables/ path; not retry same absolute path",
))

# ER05c: forgot npm run, used npm build
ER05C_MSGS = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "Build a recipe app."},
    tc("project_init", name="recipe-app"),
    tr("project_init", "Scaffolded 'recipe-app' in deliverables/recipe-app."),
    tc("file_write", path="src/App.tsx", content="export default function App() { return <div>Recipes</div> }"),
    tr("file_write", "Written."),
    tc("shell_exec", command="cd deliverables/recipe-app && npm build"),
    tr("shell_exec", "[shell_exec] Error: npm build is not a command. Did you mean: npm run build?"),
]
PAIRS.append(make_pair(ER05C_MSGS,
    chosen_fn="shell_exec",
    chosen_args={"command": "cd deliverables/recipe-app && npm run build"},
    rejected_fn="file_read",
    rejected_args={"path": "src/App.tsx"},
    source_bug="ER05-wrong-path",
    note="er05c: npm build (missing 'run') → shell_exec with npm run build; not file_read",
))


# ══════════════════════════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════════════════════════

with OUT_FILE.open("w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

# Combined with previous
prev_files = [
    Path("workspace/training_data/curator_dpo_combined_v4.jsonl"),
]
combined = []
for pf in prev_files:
    if pf.exists():
        with open(pf) as f:
            combined.extend(json.loads(l) for l in f if l.strip())
with open(OUT_FILE) as f:
    combined.extend(json.loads(l) for l in f if l.strip())

combined_path = Path("workspace/training_data/curator_dpo_combined_v5.jsonl")
with combined_path.open("w") as f:
    for p in combined:
        f.write(json.dumps(p) + "\n")

print(f"\n=== BUILD DPO v5 SUMMARY ===")
print(f"  New pairs: {len(PAIRS)}")
print(f"  Combined: {len(combined)}")
print(f"  Output: {OUT_FILE}")
print(f"  Combined: {combined_path}")
for p in PAIRS:
    print(f"  {p['source_bug']:28s}  {p['note']}")
