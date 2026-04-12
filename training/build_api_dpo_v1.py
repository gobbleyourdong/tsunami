#!/usr/bin/env python3
"""build_api_dpo_v1.py -- DPO training data for api-only-v1 adapter.

18 preference pairs targeting 6 fault patterns (3 per fault):
  APF01: api-only template (not fullstack)
  APF02: server/index.js first (not App.tsx)
  APF03: crud() factory (not raw repeated route handlers)
  APF04: curl test (not undertow -- no browser)
  APF05: no main.tsx / no React files
  APF06: file_edit on server syntax error (not file_read)
"""
import json, os, sys, datetime
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/api_dpo_v1.jsonl"
TODAY = "2026-04-12"


def tok_apply(tok, msgs):
    result = tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
    return result if isinstance(result, str) else tok.decode(result)


def sys_msg():
    return {"role": "system", "content": SYSTEM_TEXT}

def u(t):
    return {"role": "user", "content": t}

def tc(tool_name, **kw):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": tool_name, "arguments": kw}}
    ]}

def tr(tool_name, content):
    return {"role": "tool", "name": tool_name, "content": content}

SCAFFOLD_HINT = (
    "Scaffolded 'tasks-api' (api-only). Write server/index.js.\n\n"
    "## API-Only Scaffold\n"
    "Express + SQLite backend. No React frontend.\n"
    "- crud(table) registers GET/POST/PUT/DELETE /{table} + /{table}/:id\n"
    "- Dev: npm run dev (node --watch :3001)\n"
    "- Test: curl http://localhost:3001/{table}"
)

SIMPLE_SERVER = '''import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"
const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")
db.exec(`CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT DEFAULT 'open', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)`)
const app = express()
app.use(cors())
app.use(express.json())
app.get("/health", (req, res) => res.json({ ok: true }))
function crud(table) {
  const safe = table.replace(/[^a-z_]/gi, "")
  app.get(`/${safe}`, (req, res) => res.json(db.prepare(`SELECT * FROM ${safe} ORDER BY created_at DESC`).all()))
  app.get(`/${safe}/:id`, (req, res) => { const row = db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(req.params.id); row ? res.json(row) : res.status(404).json({ error: "not found" }) })
  app.post(`/${safe}`, (req, res) => { const keys = Object.keys(req.body).filter(k => k !== "id"); const vals = keys.map(k => req.body[k]); const result = db.prepare(`INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`).run(...vals); res.status(201).json({ id: result.lastInsertRowid }) })
  app.put(`/${safe}/:id`, (req, res) => { const keys = Object.keys(req.body).filter(k => k !== "id"); const vals = keys.map(k => req.body[k]); db.prepare(`UPDATE ${safe} SET ${keys.map(k => `${k}=?`).join(",")}, updated_at=CURRENT_TIMESTAMP WHERE id=?`).run(...vals, req.params.id); res.json({ ok: true }) })
  app.delete(`/${safe}/:id`, (req, res) => { db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id); res.json({ ok: true }) })
}
crud("tasks")
app.listen(PORT, () => console.log(`API: http://localhost:${PORT}`))
'''


def pair(prompt_msgs, chosen_msgs, rejected_msgs, fault_id, note):
    return {
        "prompt": prompt_msgs,
        "chosen": chosen_msgs,
        "rejected": rejected_msgs,
        "source_bug": fault_id,
        "note": note,
        "images": [],
        "date": TODAY,
    }


# ── APF01: api-only template (not fullstack) ──────────────────────────────────

def apf01_pairs():
    base_prompt = [sys_msg(), u("Build a tasks REST API -- title and status fields. Backend only, no UI.")]

    chosen_step = [tc("project_init", name="tasks-api", template="api-only")]
    rejected_step = [tc("project_init", name="tasks-api", template="fullstack")]

    rest = [
        tr("project_init", SCAFFOLD_HINT),
        tc("file_write", path="deliverables/tasks-api/server/index.js", content=SIMPLE_SERVER),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/tasks-api && npm run dev &"),
        tr("shell_exec", "API: http://localhost:3001"),
        tc("message_result", text="Tasks REST API at http://localhost:3001\n- GET/POST /tasks\n- GET/PUT/DELETE /tasks/:id"),
        tr("message_result", "Delivered."),
    ]

    return [
        pair(base_prompt, chosen_step, rejected_step, "APF01",
             "api-only: 'backend only, no UI' -> template='api-only' not 'fullstack'"),
        pair(base_prompt + [tr("project_init", SCAFFOLD_HINT)],
             [tc("file_write", path="deliverables/tasks-api/server/index.js", content=SIMPLE_SERVER)],
             [tc("file_write", path="deliverables/tasks-api/src/App.tsx", content="export default function App() { return <div>Tasks</div> }")],
             "APF01b",
             "api-only: first write is server/index.js, never App.tsx"),
        pair(
            [sys_msg(), u("Build a webhook receiver API that accepts POST /webhook and logs the payload.")],
            [tc("project_init", name="webhook-receiver", template="api-only")],
            [tc("project_init", name="webhook-receiver", template="fullstack")],
            "APF01c",
            "api-only: webhook = backend only -> template='api-only' not 'fullstack'"),
    ]


# ── APF02: server/index.js first (not App.tsx) ───────────────────────────────

def apf02_pairs():
    base = [sys_msg(), u("I need a REST API for managing project tasks. No frontend."),
            tc("project_init", name="tasks-api", template="api-only"),
            tr("project_init", SCAFFOLD_HINT)]

    return [
        pair(base,
             [tc("file_write", path="deliverables/tasks-api/server/index.js", content=SIMPLE_SERVER)],
             [tc("file_write", path="deliverables/tasks-api/src/App.tsx", content="// Should not write App.tsx for api-only")],
             "APF02",
             "api-only: after api-only scaffold, write server/index.js first (not App.tsx)"),
        pair(base + [tr("file_write", "Written: server/index.js")],
             [tc("shell_exec", command="cd deliverables/tasks-api && npm run dev &")],
             [tc("shell_exec", command="cd deliverables/tasks-api && npm run build")],
             "APF02b",
             "api-only: start server with 'npm run dev' not 'npm run build'"),
        pair(base + [tr("file_write", "Written."),
                     tc("shell_exec", command="cd deliverables/tasks-api && npm run dev &"),
                     tr("shell_exec", "API: http://localhost:3001")],
             [tc("shell_exec", command='curl -s http://localhost:3001/health')],
             [tc("undertow", url="http://localhost:3001")],
             "APF02c",
             "api-only: test with curl, not undertow (no browser to screenshot)"),
    ]


# ── APF03: crud() factory (not raw route handlers) ────────────────────────────

def apf03_pairs():
    raw_server = '''import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
const app = express()
const db = new Database("data.db")
db.exec(`CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT DEFAULT 'open', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)`)
app.use(cors())
app.use(express.json())
app.get("/tasks", (req, res) => res.json(db.prepare("SELECT * FROM tasks").all()))
app.get("/tasks/:id", (req, res) => { const row = db.prepare("SELECT * FROM tasks WHERE id = ?").get(req.params.id); row ? res.json(row) : res.status(404).json({ error: "not found" }) })
app.post("/tasks", (req, res) => { const { title, status } = req.body; const r = db.prepare("INSERT INTO tasks (title, status) VALUES (?, ?)").run(title, status || "open"); res.status(201).json({ id: r.lastInsertRowid }) })
app.put("/tasks/:id", (req, res) => { const { title, status } = req.body; db.prepare("UPDATE tasks SET title=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?").run(title, status, req.params.id); res.json({ ok: true }) })
app.delete("/tasks/:id", (req, res) => { db.prepare("DELETE FROM tasks WHERE id = ?").run(req.params.id); res.json({ ok: true }) })
app.listen(3001)
'''
    base = [sys_msg(), u("Build a tasks REST API -- title and status. Backend only."),
            tc("project_init", name="tasks-api", template="api-only"),
            tr("project_init", SCAFFOLD_HINT)]

    return [
        pair(base,
             [tc("file_write", path="deliverables/tasks-api/server/index.js", content=SIMPLE_SERVER)],
             [tc("file_write", path="deliverables/tasks-api/server/index.js", content=raw_server)],
             "APF03",
             "api-only: use crud('tablename') factory, not hardcoded route handlers per field"),
        pair(base + [tr("file_write", "Written.")],
             [tc("shell_exec", command="cd deliverables/tasks-api && npm run dev &")],
             [tc("shell_exec", command="cd deliverables/tasks-api && node server/index.js")],
             "APF03b",
             "api-only: use npm run dev (watches for changes) not node directly"),
        pair(base + [tr("file_write", "Written."),
                     tc("shell_exec", command="cd deliverables/tasks-api && npm run dev &"),
                     tr("shell_exec", "API: http://localhost:3001"),
                     tc("shell_exec", command='curl -s http://localhost:3001/health'),
                     tr("shell_exec", '{"ok":true}')],
             [tc("message_result", text="Tasks REST API at http://localhost:3001\n\nEndpoints:\n- GET    /tasks        -- list all\n- GET    /tasks/:id    -- get one\n- POST   /tasks        -- create {title, status}\n- PUT    /tasks/:id    -- update\n- DELETE /tasks/:id    -- delete")],
             [tc("undertow", url="http://localhost:3001")],
             "APF03c",
             "api-only: message_result with endpoint list, not undertow screenshot"),
    ]


# ── APF04: curl test (not undertow) ──────────────────────────────────────────

def apf04_pairs():
    base = [sys_msg(), u("Build a microservice for URL shortening -- store original URL and return a short code."),
            tc("project_init", name="url-shortener-api", template="api-only"),
            tr("project_init", SCAFFOLD_HINT.replace("tasks-api", "url-shortener-api")),
            tc("file_write", path="deliverables/url-shortener-api/server/index.js",
               content=SIMPLE_SERVER.replace("tasks", "urls").replace("title TEXT NOT NULL, status TEXT DEFAULT 'open'",
               "original_url TEXT NOT NULL, short_code TEXT UNIQUE NOT NULL, hits INTEGER DEFAULT 0")),
            tr("file_write", "Written."),
            tc("shell_exec", command="cd deliverables/url-shortener-api && npm run dev &"),
            tr("shell_exec", "API: http://localhost:3001")]

    return [
        pair(base,
             [tc("shell_exec", command='curl -s -X POST http://localhost:3001/urls -H "Content-Type: application/json" -d \'{"original_url":"https://example.com","short_code":"ex1"}\'')],
             [tc("undertow", url="http://localhost:3001")],
             "APF04",
             "api-only: test with curl POST, not undertow (no browser for pure API)"),
        pair(base + [tr("shell_exec", '{"id":1}')],
             [tc("shell_exec", command="curl -s http://localhost:3001/urls")],
             [tc("undertow", url="http://localhost:3001/urls")],
             "APF04b",
             "api-only: verify list with curl GET, not undertow"),
        pair(base + [tr("shell_exec", '{"id":1}'),
                     tc("shell_exec", command="curl -s http://localhost:3001/urls"),
                     tr("shell_exec", '[{"id":1,"original_url":"https://example.com","short_code":"ex1","hits":0}]')],
             [tc("message_result", text="URL shortener API at http://localhost:3001\n\nEndpoints:\n- POST /urls   {original_url, short_code} -- create\n- GET  /urls   -- list all\n- GET  /urls/:id -- get one")],
             [tc("undertow", url="http://localhost:3001")],
             "APF04c",
             "api-only: end with message_result listing endpoints, not undertow"),
    ]


# ── APF05: no main.tsx / no React files ──────────────────────────────────────

def apf05_pairs():
    base = [sys_msg(), u("Build a REST API for a bug tracker -- title, description, severity, status."),
            tc("project_init", name="bugtracker-api", template="api-only"),
            tr("project_init", SCAFFOLD_HINT.replace("tasks-api", "bugtracker-api"))]

    return [
        pair(base,
             [tc("file_write", path="deliverables/bugtracker-api/server/index.js", content=SIMPLE_SERVER)],
             [tc("file_write", path="deliverables/bugtracker-api/src/main.tsx",
                 content='import { createRoot } from "react-dom/client"\nimport App from "./App"\ncreateRoot(document.getElementById("root")!).render(<App />)')],
             "APF05",
             "api-only: never write main.tsx or React files for an api-only scaffold"),
        pair(base,
             [tc("file_write", path="deliverables/bugtracker-api/server/index.js", content=SIMPLE_SERVER)],
             [tc("file_write", path="deliverables/bugtracker-api/src/App.tsx",
                 content="export default function App() { return <div>Bug Tracker</div> }")],
             "APF05b",
             "api-only: never write App.tsx for api-only -- no frontend"),
        pair(base + [tr("file_write", "Written."),
                     tc("shell_exec", command="cd deliverables/bugtracker-api && npm run dev &"),
                     tr("shell_exec", "API: http://localhost:3001")],
             [tc("message_result", text="Bug tracker API at http://localhost:3001\n\nEndpoints:\n- GET/POST /bugs\n- GET/PUT/DELETE /bugs/:id")],
             [tc("file_write", path="deliverables/bugtracker-api/src/App.tsx",
                 content="// Adding a UI component")],
             "APF05c",
             "api-only: after server is running, message_result with endpoint list -- no App.tsx"),
    ]


# ── APF06: file_edit on server syntax error (not file_read) ──────────────────

def apf06_pairs():
    buggy_server = SIMPLE_SERVER.replace(
        'app.get("/health", (req, res) => res.json({ ok: true }))',
        'app.get("/health", (req, res) => res.json({ ok: true })'  # missing close paren
    )

    base = [sys_msg(), u("Build a tasks REST API."),
            tc("project_init", name="tasks-api", template="api-only"),
            tr("project_init", SCAFFOLD_HINT),
            tc("file_write", path="deliverables/tasks-api/server/index.js", content=buggy_server),
            tr("file_write", "Written."),
            tc("shell_exec", command="cd deliverables/tasks-api && node server/index.js"),
            tr("shell_exec", 'SyntaxError: Unexpected identifier \'function\' -- missing \')\' to close \'(\' at app.get("/health"'),
    ]

    return [
        pair(base,
             [tc("file_edit", path="deliverables/tasks-api/server/index.js",
                 old_text='app.get("/health", (req, res) => res.json({ ok: true })\nfunction',
                 new_text='app.get("/health", (req, res) => res.json({ ok: true }))\nfunction')],
             [tc("file_read", path="deliverables/tasks-api/server/index.js")],
             "APF06",
             "api-only: syntax error with line info -> file_edit directly, not file_read"),
        pair(base + [tc("file_edit", path="deliverables/tasks-api/server/index.js",
                        old_text='app.get("/health", (req, res) => res.json({ ok: true })\nfunction',
                        new_text='app.get("/health", (req, res) => res.json({ ok: true }))\nfunction'),
                     tr("file_edit", "Edited.")],
             [tc("shell_exec", command="cd deliverables/tasks-api && npm run dev &")],
             [tc("file_read", path="deliverables/tasks-api/server/index.js")],
             "APF06b",
             "api-only: after fixing syntax, restart server -- not file_read again"),
        pair([sys_msg(), u("Build a tasks REST API."),
              tc("project_init", name="tasks-api2", template="api-only"),
              tr("project_init", SCAFFOLD_HINT.replace("tasks-api'", "tasks-api2'")),
              tc("file_write", path="deliverables/tasks-api2/server/index.js", content=SIMPLE_SERVER),
              tr("file_write", "Written."),
              tc("shell_exec", command="cd deliverables/tasks-api2 && node server/index.js"),
              tr("shell_exec", 'ReferenceError: db is not defined at /deliverables/tasks-api2/server/index.js:6:17 -- db must be declared before use')],
             [tc("file_edit", path="deliverables/tasks-api2/server/index.js",
                 old_text="const app = express()\nconst db = new Database",
                 new_text="const db = new Database")],
             [tc("file_read", path="deliverables/tasks-api2/server/index.js")],
             "APF06c",
             "api-only: runtime error with line number -> file_edit to fix, not file_read"),
    ]


def main():
    print("Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    all_pairs = []
    for fn in [apf01_pairs, apf02_pairs, apf03_pairs, apf04_pairs, apf05_pairs, apf06_pairs]:
        pairs = fn()
        for p in pairs:
            p["prompt"] = tok_apply(tok, p["prompt"])
            p["chosen"] = tok_apply(tok, p["chosen"])
            p["rejected"] = tok_apply(tok, p["rejected"])
        all_pairs.extend(pairs)
        print(f"  {fn.__name__}: {len(pairs)} pairs")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")

    print(f"\nTotal: {len(all_pairs)} pairs")
    print(f"Wrote to {OUT_PATH}")


if __name__ == "__main__":
    main()
