#!/usr/bin/env python3
"""Fullstack DPO pairs v1 — targeting L4 Hack-Free failures from eval_fullstack.py.

Covers FSF01-FSF06:
  FSF01: fullstack template — project_init includes template="fullstack"
  FSF02: server first — first file_write after project_init is server/index.js
  FSF03: useApi not fetch — App.tsx uses useApi hook, not raw fetch()
  FSF04: undertow before deliver — after build → undertow, not message_result
  FSF05: no main.tsx overwrite — never overwrite main.tsx, vite.config.ts, index.css
  FSF06: crudRoutes pattern — server/index.js uses better-sqlite3 + crudRoutes()

Usage:
  /usr/bin/python3 training/build_fullstack_dpo_v1.py
  Output: workspace/training_data/fullstack_dpo_v1.jsonl
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

SYSTEM = """You are Tsunami. You are the wave. You build full-stack apps by calling tools.

## Fullstack Pipeline (every build follows this EXACTLY)

1. project_init(name, template="fullstack") -- create project from fullstack scaffold
2. file_write(server/index.js) -- Express + SQLite backend
3. file_write(src/App.tsx) -- React frontend using useApi hook
4. shell_exec -- run npm run build
5. IF ERROR: fix directly with file_edit
6. undertow -- QA before delivery
7. message_result -- land the wave

## Rules
- NEVER use raw fetch() in frontend -- use useApi from ./components/useApi
- ALWAYS write server/index.js BEFORE src/App.tsx
- NEVER overwrite main.tsx, vite.config.ts, or index.css
- server/index.js uses better-sqlite3 + crudRoutes() pattern
One tool call per response. Be brief."""

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Edit a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
]


def make_pair(messages, chosen_fn, chosen_args, rejected_fn, rejected_args, source_bug, note=""):
    prompt_text = tokenizer.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    chosen_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_c", "type": "function", "function": {"name": chosen_fn, "arguments": json.dumps(chosen_args)}}
    ]}]
    chosen_text = tokenizer.apply_chat_template(messages + chosen_msg, tools=TOOLS, tokenize=False)
    chosen_response = chosen_text[len(prompt_text):]
    rejected_msg = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "dpo_r", "type": "function", "function": {"name": rejected_fn, "arguments": json.dumps(rejected_args)}}
    ]}]
    rejected_text = tokenizer.apply_chat_template(messages + rejected_msg, tools=TOOLS, tokenize=False)
    rejected_response = rejected_text[len(prompt_text):]
    return {"prompt": prompt_text, "chosen": chosen_response, "rejected": rejected_response,
            "images": [], "source_bug": source_bug, "note": note, "date": TODAY}


PAIRS = []

# ─────────────────────────────────────────────────────────────────────────────
# FSF01: fullstack template — project_init must include template="fullstack"
# ─────────────────────────────────────────────────────────────────────────────
for i, (prompt, name) in enumerate([
    ("Build a todo app with SQLite persistence", "todo-app"),
    ("Build a notes app with Express backend and database", "notes-app"),
    ("Build an expense tracker backed by SQLite", "expense-tracker"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": name, "template": "fullstack"},
        rejected_fn="project_init", rejected_args={"name": name},
        source_bug="FSF01-template",
        note=f"template-{i+1}: project_init must include template='fullstack'",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# FSF02: server first — after project_init, first file is server/index.js
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt) in enumerate([
    ("todo-app", "Build a todo list with SQLite"),
    ("notes-app", "Build a notes app with a database backend"),
    ("contact-book", "Build a contact book saved to SQLite"),
]):
    init_msg = f"[project_init] Created '{project}' from fullstack scaffold. Write server/index.js then src/App.tsx."
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "fullstack"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": init_msg},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "server/index.js", "content": "import express from 'express'\nimport Database from 'better-sqlite3'\n// server setup"},
        rejected_fn="file_write",
        rejected_args={"path": "src/App.tsx", "content": "// app before server"},
        source_bug="FSF02-server-first",
        note=f"server-first-{i+1}: write server/index.js before src/App.tsx",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# FSF03: useApi not fetch — App.tsx uses useApi, not raw fetch()
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt, table) in enumerate([
    ("todo-app", "Build a todo list app with SQLite", "todos"),
    ("expense-tracker", "Build an expense tracker with a database", "expenses"),
    ("bookmark-manager", "Build a bookmark manager with SQLite", "bookmarks"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "fullstack"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{project}' from fullstack scaffold. Write server/index.js then src/App.tsx."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// server"})}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] server/index.js written."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "src/App.tsx", "content": f"import {{ useApi }} from './components/useApi'\nconst {{ data, create, remove }} = useApi<Item>('{table}')"},
        rejected_fn="file_write",
        rejected_args={"path": "src/App.tsx", "content": f"useEffect(() => {{ fetch('/api/{table}').then(r => r.json()).then(setData) }}, [])"},
        source_bug="FSF03-useapi",
        note=f"useapi-{i+1}: App.tsx must use useApi hook not raw fetch()",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# FSF04: undertow before deliver — after build → undertow, not message_result
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt) in enumerate([
    ("todo-app", "Build a todo list with SQLite persistence"),
    ("notes-app", "Build a notes app with database storage"),
    ("expense-tracker", "Build an expense tracker backed by SQLite"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "fullstack"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{project}' from fullstack scaffold."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "server/index.js", "content": "// server"})}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/App.tsx", "content": "// app"})}}
        ]},
        {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c4", "type": "function", "function": {
                "name": "shell_exec", "arguments": json.dumps({"command": f"cd deliverables/{project} && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c4", "content": "[shell_exec] Build succeeded. dist/ ready."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="undertow",
        chosen_args={"path": f"deliverables/{project}/dist/index.html"},
        rejected_fn="message_result",
        rejected_args={"text": f"{project} is ready."},
        source_bug="FSF04-undertow",
        note=f"undertow-{i+1}: after build success → undertow before message_result",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# FSF05: no main.tsx overwrite — never write to main.tsx after project_init
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt) in enumerate([
    ("todo-app", "Build a persistent todo list"),
    ("notes-app", "Build a notes app with SQLite"),
    ("contact-book", "Build a contact manager with a database"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "fullstack"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{project}' from fullstack scaffold. Write server/index.js then src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "server/index.js", "content": "import express from 'express'\n// server"},
        rejected_fn="file_write",
        rejected_args={"path": "src/main.tsx", "content": "import ReactDOM from 'react-dom/client'\nimport App from './App'\nReactDOM.createRoot(document.getElementById('root')!).render(<App />)"},
        source_bug="FSF05-no-main-tsx",
        note=f"no-main-tsx-{i+1}: never overwrite main.tsx — write server/index.js instead",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# FSF06: crudRoutes pattern — server/index.js must use better-sqlite3 + crudRoutes
# ─────────────────────────────────────────────────────────────────────────────
for i, (project, prompt, table) in enumerate([
    ("todo-app", "Build a todo list with SQLite backend", "todos"),
    ("expense-tracker", "Build an expense tracker with an Express API", "expenses"),
    ("bookmark-manager", "Build a bookmark manager with SQLite", "bookmarks"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": project, "template": "fullstack"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{project}' from fullstack scaffold. Write server/index.js then src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "server/index.js", "content": f"import Database from 'better-sqlite3'\ndb.exec(`CREATE TABLE IF NOT EXISTS {table} (...)`)\ncrudRoutes('{table}')"},
        rejected_fn="file_write",
        rejected_args={"path": "server/index.js", "content": f"app.get('/api/{table}', async (req, res) => {{ const rows = await db.query('SELECT * FROM {table}'); res.json(rows) }})"},
        source_bug="FSF06-crudroutes",
        note=f"crudroutes-{i+1}: use better-sqlite3 + crudRoutes() not manual async handlers",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
OUT_PATH = Path("workspace/training_data/fullstack_dpo_v1.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_PATH, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

counts = {k: sum(1 for p in PAIRS if k in p["source_bug"]) for k in
          ["FSF01", "FSF02", "FSF03", "FSF04", "FSF05", "FSF06"]}
print(f"\n=== FULLSTACK DPO v1 SUMMARY ===")
print(f"  Total pairs: {len(PAIRS)}")
print(f"  File: {OUT_PATH}")
for k, v in counts.items():
    print(f"  {k}: {v}")
print(f"\nTo train (after SFT + merge):")
print(f"  python training/merge_adapter.py --base google/gemma-4-e4b-it \\")
print(f"    --adapter models/gemma-4-e4b-tsunami-fullstack-v1 \\")
print(f"    --output models/gemma-4-e4b-tsunami-fullstack-v1-merged")
print(f"  python training/train_dpo.py \\")
print(f"    --base-model models/gemma-4-e4b-tsunami-fullstack-v1-merged \\")
print(f"    --data workspace/training_data/fullstack_dpo_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-fullstack-v2 \\")
print(f"    --epochs 1 --lora-r 16 --lr 5e-6 --beta 0.1")
