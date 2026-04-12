#!/usr/bin/env python3
"""build_api_sft_v1.py -- SFT training data for api-only-v1 adapter.

Express + SQLite, no React frontend. 6 full trajectories:
  AP01: todo REST API (basic CRUD)
  AP02: bookmarks API (CRUD + tags)
  AP03: products/inventory API
  AP04: users API (email, role, status)
  AP05: error recovery (syntax error -> file_edit directly)
  AP06: conversational (add search endpoint follow-up)

Model learns:
  1. project_init(template="api-only") -- not fullstack or react-app
  2. Write ONLY server/index.js -- never App.tsx, never main.tsx
  3. Use crud("tablename") factory for standard CRUD routes
  4. Test with shell_exec + curl -- NOT undertow (no browser)
  5. Return endpoint list in message_result
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/api_sft_v1.jsonl"


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
    "Scaffolded (api-only). Write server/index.js.\n\n"
    "## API-Only Scaffold\n"
    "Express + SQLite backend. No React frontend.\n"
    "- crud(table) registers GET/POST/PUT/DELETE /{table} + /{table}/:id\n"
    "- Dev: npm run dev (node --watch :3001)\n"
    "- Test: curl http://localhost:3001/{table}"
)

SERVER_TMPL = '''import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import {{ dirname, join }} from "path"
import {{ fileURLToPath }} from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")
db.pragma("foreign_keys = ON")

db.exec(`
  CREATE TABLE IF NOT EXISTS {table} ({schema})
`)

const app = express()
app.use(cors())
app.use(express.json())

app.get("/health", (req, res) => res.json({{ ok: true }}))

function crud(table) {{
  const safe = table.replace(/[^a-z_]/gi, "")
  app.get(`/${{safe}}`, (req, res) => {{
    res.json(db.prepare(`SELECT * FROM ${{safe}} ORDER BY created_at DESC`).all())
  }})
  app.get(`/${{safe}}/:id`, (req, res) => {{
    const row = db.prepare(`SELECT * FROM ${{safe}} WHERE id = ?`).get(req.params.id)
    row ? res.json(row) : res.status(404).json({{ error: "not found" }})
  }})
  app.post(`/${{safe}}`, (req, res) => {{
    const keys = Object.keys(req.body).filter(k => k !== "id")
    const vals = keys.map(k => req.body[k])
    const result = db.prepare(
      `INSERT INTO ${{safe}} (${{keys.join(",")}}) VALUES (${{keys.map(() => "?").join(",")}})`
    ).run(...vals)
    res.status(201).json({{ id: result.lastInsertRowid }})
  }})
  app.put(`/${{safe}}/:id`, (req, res) => {{
    const keys = Object.keys(req.body).filter(k => k !== "id")
    const vals = keys.map(k => req.body[k])
    db.prepare(
      `UPDATE ${{safe}} SET ${{keys.map(k => `${{k}}=?`).join(",")}}, updated_at=CURRENT_TIMESTAMP WHERE id=?`
    ).run(...vals, req.params.id)
    res.json({{ ok: true }})
  }})
  app.delete(`/${{safe}}/:id`, (req, res) => {{
    db.prepare(`DELETE FROM ${{safe}} WHERE id = ?`).run(req.params.id)
    res.json({{ ok: true }})
  }})
}}

crud("{table}")
app.listen(PORT, () => console.log(`API: http://localhost:${{PORT}}`))
'''


def ap01_todo_api():
    schema = """id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done INTEGER DEFAULT 0,
    priority TEXT DEFAULT 'medium',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"""
    content = SERVER_TMPL.format(table="todos", schema=schema)
    return [
        sys_msg(),
        u("Build a REST API for todos with title, done status, and priority. I just need the backend."),
        tc("project_init", name="todos-api", template="api-only"),
        tr("project_init", SCAFFOLD_HINT.replace("Scaffolded", "Scaffolded 'todos-api'")),
        tc("file_write", path="deliverables/todos-api/server/index.js", content=content),
        tr("file_write", "Written: deliverables/todos-api/server/index.js"),
        tc("shell_exec", command="cd deliverables/todos-api && npm run dev &"),
        tr("shell_exec", "API: http://localhost:3001"),
        tc("shell_exec", command='curl -s http://localhost:3001/health'),
        tr("shell_exec", '{"ok":true}'),
        tc("shell_exec", command='curl -s -X POST http://localhost:3001/todos -H "Content-Type: application/json" -d \'{"title":"Buy milk","done":0,"priority":"high"}\''),
        tr("shell_exec", '{"id":1}'),
        tc("shell_exec", command="curl -s http://localhost:3001/todos"),
        tr("shell_exec", '[{"id":1,"title":"Buy milk","done":0,"priority":"high","created_at":"...","updated_at":"..."}]'),
        tc("message_result", text="Todo REST API at http://localhost:3001\n\nEndpoints:\n- GET    /todos        -- list all\n- GET    /todos/:id    -- get one\n- POST   /todos        -- create {title, done, priority}\n- PUT    /todos/:id    -- update fields\n- DELETE /todos/:id    -- delete\n- GET    /health       -- health check"),
        tr("message_result", "Delivered."),
    ]


def ap02_bookmarks_api():
    schema = """id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    tags TEXT DEFAULT '',
    favorite INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"""
    content = SERVER_TMPL.format(table="bookmarks", schema=schema)
    return [
        sys_msg(),
        u("Build a bookmarks REST API. Each bookmark has a URL, title, optional tags, and a favorite flag."),
        tc("project_init", name="bookmarks-api", template="api-only"),
        tr("project_init", SCAFFOLD_HINT.replace("Scaffolded", "Scaffolded 'bookmarks-api'")),
        tc("file_write", path="deliverables/bookmarks-api/server/index.js", content=content),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/bookmarks-api && npm run dev &"),
        tr("shell_exec", "API: http://localhost:3001"),
        tc("shell_exec", command='curl -s -X POST http://localhost:3001/bookmarks -H "Content-Type: application/json" -d \'{"url":"https://github.com","title":"GitHub","tags":"dev,code","favorite":1}\''),
        tr("shell_exec", '{"id":1}'),
        tc("shell_exec", command="curl -s http://localhost:3001/bookmarks"),
        tr("shell_exec", '[{"id":1,"url":"https://github.com","title":"GitHub","tags":"dev,code","favorite":1,"created_at":"..."}]'),
        tc("message_result", text="Bookmarks REST API at http://localhost:3001\n\nEndpoints:\n- GET    /bookmarks        -- list all\n- GET    /bookmarks/:id    -- get one\n- POST   /bookmarks        -- create {url, title, tags, favorite}\n- PUT    /bookmarks/:id    -- update\n- DELETE /bookmarks/:id    -- delete\n\nStore tags as comma-separated string, e.g. 'dev,reference'"),
        tr("message_result", "Delivered."),
    ]


def ap03_products_api():
    schema = """id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL DEFAULT 0,
    stock INTEGER NOT NULL DEFAULT 0,
    category TEXT DEFAULT 'uncategorized',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"""
    content = SERVER_TMPL.format(table="products", schema=schema)
    return [
        sys_msg(),
        u("Build a REST API for a product inventory. Products have name, price, stock quantity, and category."),
        tc("project_init", name="inventory-api", template="api-only"),
        tr("project_init", SCAFFOLD_HINT.replace("Scaffolded", "Scaffolded 'inventory-api'")),
        tc("file_write", path="deliverables/inventory-api/server/index.js", content=content),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/inventory-api && npm run dev &"),
        tr("shell_exec", "API: http://localhost:3001"),
        tc("shell_exec", command='curl -s -X POST http://localhost:3001/products -H "Content-Type: application/json" -d \'{"name":"Widget A","price":29.99,"stock":10,"category":"widgets"}\''),
        tr("shell_exec", '{"id":1}'),
        tc("shell_exec", command="curl -s http://localhost:3001/products"),
        tr("shell_exec", '[{"id":1,"name":"Widget A","price":29.99,"stock":10,"category":"widgets","created_at":"..."}]'),
        tc("message_result", text="Inventory REST API at http://localhost:3001\n\nEndpoints:\n- GET    /products        -- list all (newest first)\n- GET    /products/:id    -- get one\n- POST   /products        -- create {name, price, stock, category}\n- PUT    /products/:id    -- update\n- DELETE /products/:id    -- delete\n\nFields: name, price (REAL), stock (INTEGER), category"),
        tr("message_result", "Delivered."),
    ]


def ap04_users_api():
    schema = """id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"""
    content = SERVER_TMPL.format(table="users", schema=schema)
    return [
        sys_msg(),
        u("Build a REST API for user management. Users have email, display name, role (admin/user/viewer), and active status."),
        tc("project_init", name="users-api", template="api-only"),
        tr("project_init", SCAFFOLD_HINT.replace("Scaffolded", "Scaffolded 'users-api'")),
        tc("file_write", path="deliverables/users-api/server/index.js", content=content),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/users-api && npm run dev &"),
        tr("shell_exec", "API: http://localhost:3001"),
        tc("shell_exec", command='curl -s -X POST http://localhost:3001/users -H "Content-Type: application/json" -d \'{"email":"alice@example.com","display_name":"Alice","role":"admin","active":1}\''),
        tr("shell_exec", '{"id":1}'),
        tc("shell_exec", command="curl -s http://localhost:3001/users"),
        tr("shell_exec", '[{"id":1,"email":"alice@example.com","display_name":"Alice","role":"admin","active":1,"created_at":"..."}]'),
        tc("message_result", text="Users REST API at http://localhost:3001\n\nEndpoints:\n- GET    /users        -- list all\n- GET    /users/:id    -- get one\n- POST   /users        -- create {email, display_name, role, active}\n- PUT    /users/:id    -- update\n- DELETE /users/:id    -- delete\n\nFields: email (UNIQUE), display_name, role (admin/user/viewer), active (0/1)"),
        tr("message_result", "Delivered."),
    ]


def ap05_error_recovery():
    """Syntax error in server/index.js -> file_edit directly."""
    return [
        sys_msg(),
        u("Build a notes REST API -- title, body, pinned flag."),
        tc("project_init", name="notes-api", template="api-only"),
        tr("project_init", SCAFFOLD_HINT.replace("Scaffolded", "Scaffolded 'notes-api'")),
        # Intentional bug: missing closing paren on health route
        tc("file_write", path="deliverables/notes-api/server/index.js",
           content='import express from "express"\nimport cors from "cors"\nimport Database from "better-sqlite3"\nconst app = express()\nconst db = new Database("data.db")\ndb.exec(`CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT DEFAULT \'\', pinned INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)`)\napp.use(cors())\napp.use(express.json())\napp.get("/health", (req, res) => res.json({ ok: true })\nfunction crud(table) { const safe = table.replace(/[^a-z_]/gi, ""); app.get(`/${safe}`, (req, res) => { res.json(db.prepare(`SELECT * FROM ${safe} ORDER BY pinned DESC, created_at DESC`).all()) }); app.get(`/${safe}/:id`, (req, res) => { const row = db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(req.params.id); row ? res.json(row) : res.status(404).json({ error: "not found" }) }); app.post(`/${safe}`, (req, res) => { const keys = Object.keys(req.body).filter(k => k !== "id"); const vals = keys.map(k => req.body[k]); const result = db.prepare(`INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`).run(...vals); res.status(201).json({ id: result.lastInsertRowid }) }); app.put(`/${safe}/:id`, (req, res) => { const keys = Object.keys(req.body).filter(k => k !== "id"); const vals = keys.map(k => req.body[k]); db.prepare(`UPDATE ${safe} SET ${keys.map(k => `${k}=?`).join(",")}, updated_at=CURRENT_TIMESTAMP WHERE id=?`).run(...vals, req.params.id); res.json({ ok: true }) }); app.delete(`/${safe}/:id`, (req, res) => { db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id); res.json({ ok: true }) }) }\ncrud("notes")\napp.listen(3001, () => console.log("API: http://localhost:3001"))\n'),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/notes-api && node server/index.js"),
        tr("shell_exec", 'SyntaxError: Unexpected identifier \'function\' -- missing \')\' to close \'(\' at line starting with app.get("/health"'),
        # Fix: missing close paren on health route
        tc("file_edit", path="deliverables/notes-api/server/index.js",
           old_text='app.get("/health", (req, res) => res.json({ ok: true })\nfunction',
           new_text='app.get("/health", (req, res) => res.json({ ok: true }))\nfunction'),
        tr("file_edit", "Edited."),
        tc("shell_exec", command="cd deliverables/notes-api && npm run dev &"),
        tr("shell_exec", "API: http://localhost:3001"),
        tc("shell_exec", command='curl -s http://localhost:3001/health'),
        tr("shell_exec", '{"ok":true}'),
        tc("message_result", text="Notes REST API at http://localhost:3001\n\nEndpoints:\n- GET    /notes        -- list (pinned first)\n- GET    /notes/:id    -- get one\n- POST   /notes        -- create {title, body, pinned}\n- PUT    /notes/:id    -- update\n- DELETE /notes/:id    -- delete"),
        tr("message_result", "Delivered."),
    ]


def ap06_conversational():
    """Add search endpoint to existing API as a follow-up."""
    schema = """id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    location TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"""
    content = SERVER_TMPL.format(table="events", schema=schema)
    return [
        sys_msg(),
        u("Build a REST API for events -- name, date, location, category."),
        tc("project_init", name="events-api", template="api-only"),
        tr("project_init", SCAFFOLD_HINT.replace("Scaffolded", "Scaffolded 'events-api'")),
        tc("file_write", path="deliverables/events-api/server/index.js", content=content),
        tr("file_write", "Written."),
        tc("shell_exec", command="cd deliverables/events-api && npm run dev &"),
        tr("shell_exec", "API: http://localhost:3001"),
        tc("message_result", text="Events REST API at http://localhost:3001\n\nEndpoints:\n- GET    /events        -- list all (ordered by created_at)\n- GET    /events/:id    -- get one\n- POST   /events        -- create {name, date, location, category}\n- PUT    /events/:id    -- update\n- DELETE /events/:id    -- delete"),
        tr("message_result", "Delivered."),
        u("Can you add a search endpoint? I want to search by name or location."),
        tc("file_edit", path="deliverables/events-api/server/index.js",
           old_text='crud("events")\napp.listen(PORT, () => console.log(`API: http://localhost:${PORT}`))',
           new_text='crud("events")\n\napp.get("/events/search", (req, res) => {\n  const { q } = req.query\n  if (!q) return res.json([])\n  const term = `%${q}%`\n  const rows = db.prepare(\n    "SELECT * FROM events WHERE name LIKE ? OR location LIKE ? ORDER BY date"\n  ).all(term, term)\n  res.json(rows)\n})\n\napp.listen(PORT, () => console.log(`API: http://localhost:${PORT}`))'),
        tr("file_edit", "Edited."),
        tc("shell_exec", command="curl -s 'http://localhost:3001/events/search?q=downtown'"),
        tr("shell_exec", "[]"),
        tc("message_result", text="Added search endpoint:\n- GET /events/search?q=<term>  -- search name and location (case-insensitive, partial match)"),
        tr("message_result", "Delivered."),
    ]


def main():
    print("Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    builders = [
        ap01_todo_api,
        ap02_bookmarks_api,
        ap03_products_api,
        ap04_users_api,
        ap05_error_recovery,
        ap06_conversational,
    ]

    examples = []
    for fn in builders:
        msgs = fn()
        text = tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        if not isinstance(text, str):
            text = tok.decode(text)
        examples.append({"text": text, "source": fn.__name__})
        print(f"  {fn.__name__}: {len(msgs)} messages -> {len(text)} chars")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    print(f"\nTotal: {len(examples)} examples")
    print(f"Wrote to {OUT_PATH}")


if __name__ == "__main__":
    main()
