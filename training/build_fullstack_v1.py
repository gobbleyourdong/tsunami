#!/usr/bin/env python3
"""Fullstack adapter SFT v1 — 6 examples for the fullstack scaffold.

Scaffold: Vite + React + Express + SQLite (better-sqlite3)
Files to write per build:
  1. server/index.js  — Express + SQLite tables + crudRoutes()
  2. src/App.tsx      — React frontend using useApi hook from ./components/useApi
Build: npm run build (vite, NOT electron:build)
QA: undertow → message_result

Usage:
  /usr/bin/python3 training/build_fullstack_v1.py
  Output: workspace/training_data/fullstack_sft_v1.jsonl
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

FS_SYSTEM = """You are Tsunami. You are the wave. You build full-stack apps by calling tools.

## Fullstack Pipeline (every build follows this EXACTLY)

1. project_init(name, template="fullstack") -- create project from fullstack scaffold
2. file_write(server/index.js) -- Express + SQLite backend (tables + crudRoutes)
3. file_write(src/App.tsx) -- React frontend using useApi hook
4. shell_exec -- run npm run build
5. IF ERROR: fix directly with file_edit
6. undertow -- QA before delivery
7. message_result -- land the wave

## Backend Pattern (server/index.js)

```js
import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
// ... db setup, crudRoutes ...
db.exec(`CREATE TABLE IF NOT EXISTS todos (...)`)
crudRoutes("todos")
app.listen(PORT)
```

## Frontend Pattern (src/App.tsx)

```tsx
import { useApi } from './components/useApi'
const { data, loading, error, create, update, remove } = useApi<Todo>("todos")
```

## Rules
- NEVER use raw fetch() in frontend -- use useApi hook
- ALWAYS write server/index.js BEFORE src/App.tsx
- NEVER overwrite main.tsx, vite.config.ts, or index.css
- One tool call per response. Be brief.
"""

FS_TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project from the scaffold library.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file with full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications to an existing file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
]

FS01_SERVER = """\
import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")
db.pragma("foreign_keys = ON")

db.exec(`
  CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    done INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`)

const app = express()
app.use(cors())
app.use(express.json())
app.get("/api/health", (req, res) => res.json({ ok: true }))

function crudRoutes(table) {
  const safe = table.replace(/[^a-z_]/gi, "")
  app.get(`/api/${safe}`, (req, res) => {
    try { res.json(db.prepare(`SELECT * FROM ${safe} ORDER BY created_at DESC`).all()) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.post(`/api/${safe}`, (req, res) => {
    try {
      const keys = Object.keys(req.body)
      const stmt = db.prepare(`INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`)
      const info = stmt.run(...Object.values(req.body))
      res.json(db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(info.lastInsertRowid))
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.put(`/api/${safe}/:id`, (req, res) => {
    try {
      const sets = Object.keys(req.body).map(k => `${k} = ?`).join(", ")
      db.prepare(`UPDATE ${safe} SET ${sets} WHERE id = ?`).run(...Object.values(req.body), req.params.id)
      res.json(db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(req.params.id))
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.delete(`/api/${safe}/:id`, (req, res) => {
    try { db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id); res.json({ ok: true }) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
}

crudRoutes("todos")
app.listen(PORT, () => console.log(`Server on :${PORT}`))
"""

FS01_APP = """\
import "./index.css"
import { useState } from "react"
import { useApi } from "./components/useApi"

interface Todo {
  id: number
  text: string
  done: number
  created_at: string
}

export default function App() {
  const { data: todos, loading, error, create, update, remove } = useApi<Todo>("todos")
  const [input, setInput] = useState("")

  const add = async () => {
    if (!input.trim()) return
    await create({ text: input, done: 0 })
    setInput("")
  }

  const toggle = (t: Todo) => update(t.id, { done: t.done ? 0 : 1 })

  if (loading) return <div className="p-8">Loading...</div>
  if (error) return <div className="p-8 text-red-500">{error}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-8 max-w-lg mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">Todo List</h1>
      <div className="flex gap-2 mb-6">
        <input
          className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && add()}
          placeholder="Add a task..."
        />
        <button className="bg-blue-500 text-white px-4 py-2 rounded text-sm hover:bg-blue-600" onClick={add}>Add</button>
      </div>
      <ul className="space-y-2">
        {(todos || []).map(t => (
          <li key={t.id} className="flex items-center gap-3 bg-white border border-gray-200 rounded px-4 py-3">
            <input type="checkbox" checked={!!t.done} onChange={() => toggle(t)} className="w-4 h-4" />
            <span className={t.done ? "line-through text-gray-400 flex-1 text-sm" : "flex-1 text-sm text-gray-700"}>{t.text}</span>
            <button className="text-red-400 hover:text-red-600 text-xs" onClick={() => remove(t.id)}>Delete</button>
          </li>
        ))}
      </ul>
      {(todos || []).length === 0 && <p className="text-gray-400 text-sm text-center mt-8">No tasks yet.</p>}
    </div>
  )
}
"""

FS02_SERVER = """\
import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")

db.exec(`
  CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`)

const app = express()
app.use(cors())
app.use(express.json())
app.get("/api/health", (req, res) => res.json({ ok: true }))

function crudRoutes(table) {
  const safe = table.replace(/[^a-z_]/gi, "")
  app.get(`/api/${safe}`, (req, res) => {
    try { res.json(db.prepare(`SELECT * FROM ${safe} ORDER BY updated_at DESC`).all()) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.post(`/api/${safe}`, (req, res) => {
    try {
      const keys = Object.keys(req.body)
      const info = db.prepare(`INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`).run(...Object.values(req.body))
      res.json(db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(info.lastInsertRowid))
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.put(`/api/${safe}/:id`, (req, res) => {
    try {
      const extra = { updated_at: new Date().toISOString() }
      const body = { ...req.body, ...extra }
      const sets = Object.keys(body).map(k => `${k} = ?`).join(", ")
      db.prepare(`UPDATE ${safe} SET ${sets} WHERE id = ?`).run(...Object.values(body), req.params.id)
      res.json(db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(req.params.id))
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.delete(`/api/${safe}/:id`, (req, res) => {
    try { db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id); res.json({ ok: true }) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
}

crudRoutes("notes")
app.listen(PORT, () => console.log(`Server on :${PORT}`))
"""

FS02_APP = """\
import "./index.css"
import { useState } from "react"
import { useApi } from "./components/useApi"

interface Note {
  id: number
  title: string
  content: string
  updated_at: string
}

export default function App() {
  const { data: notes, loading, error, create, update, remove } = useApi<Note>("notes")
  const [selected, setSelected] = useState<Note | null>(null)
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")

  const newNote = async () => {
    const n = await create({ title: "New Note", content: "" })
    setSelected(n)
    setTitle("New Note")
    setContent("")
  }

  const save = async () => {
    if (!selected) return
    const updated = await update(selected.id, { title, content })
    setSelected(updated)
  }

  const selectNote = (n: Note) => {
    setSelected(n)
    setTitle(n.title)
    setContent(n.content)
  }

  if (loading) return <div className="p-8">Loading...</div>
  if (error) return <div className="p-8 text-red-500">{error}</div>

  return (
    <div className="flex min-h-screen bg-gray-100">
      <aside className="w-64 bg-white border-r border-gray-200 p-4 flex flex-col gap-2">
        <button className="bg-blue-500 text-white rounded px-3 py-1.5 text-sm hover:bg-blue-600 mb-2" onClick={newNote}>+ New Note</button>
        {(notes || []).map(n => (
          <div
            key={n.id}
            onClick={() => selectNote(n)}
            className={`cursor-pointer rounded px-3 py-2 text-sm truncate ${selected?.id === n.id ? "bg-blue-50 text-blue-700 font-medium" : "text-gray-700 hover:bg-gray-50"}`}
          >{n.title}</div>
        ))}
      </aside>
      <main className="flex-1 p-8">
        {selected ? (
          <div className="max-w-2xl">
            <input className="w-full text-2xl font-bold border-b border-gray-200 pb-2 mb-4 focus:outline-none" value={title} onChange={e => setTitle(e.target.value)} placeholder="Note title" />
            <textarea className="w-full h-96 text-sm text-gray-700 focus:outline-none resize-none" value={content} onChange={e => setContent(e.target.value)} placeholder="Write your note..." />
            <div className="flex gap-2 mt-4">
              <button className="bg-blue-500 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-600" onClick={save}>Save</button>
              <button className="text-red-400 hover:text-red-600 text-sm" onClick={() => { remove(selected.id); setSelected(null) }}>Delete</button>
            </div>
          </div>
        ) : <p className="text-gray-400">Select a note or create one.</p>}
      </main>
    </div>
  )
}
"""

FS03_SERVER = """\
import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")

db.exec(`
  CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    date TEXT DEFAULT (date('now')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`)

const app = express()
app.use(cors())
app.use(express.json())
app.get("/api/health", (req, res) => res.json({ ok: true }))

function crudRoutes(table) {
  const safe = table.replace(/[^a-z_]/gi, "")
  app.get(`/api/${safe}`, (req, res) => {
    try { res.json(db.prepare(`SELECT * FROM ${safe} ORDER BY date DESC, created_at DESC`).all()) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.post(`/api/${safe}`, (req, res) => {
    try {
      const keys = Object.keys(req.body)
      const info = db.prepare(`INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`).run(...Object.values(req.body))
      res.json(db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(info.lastInsertRowid))
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.delete(`/api/${safe}/:id`, (req, res) => {
    try { db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id); res.json({ ok: true }) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
}

crudRoutes("expenses")
app.listen(PORT, () => console.log(`Server on :${PORT}`))
"""

FS03_APP = """\
import "./index.css"
import { useState } from "react"
import { useApi } from "./components/useApi"

interface Expense {
  id: number
  description: string
  amount: number
  category: string
  date: string
}

const CATEGORIES = ["food", "transport", "entertainment", "health", "shopping", "other"]

export default function App() {
  const { data: expenses, loading, error, create, remove } = useApi<Expense>("expenses")
  const [desc, setDesc] = useState("")
  const [amount, setAmount] = useState("")
  const [category, setCategory] = useState("other")

  const add = async () => {
    if (!desc.trim() || !amount) return
    await create({ description: desc, amount: parseFloat(amount), category })
    setDesc("")
    setAmount("")
  }

  const total = (expenses || []).reduce((s, e) => s + e.amount, 0)
  const byCategory = CATEGORIES.map(c => ({
    c,
    sum: (expenses || []).filter(e => e.category === c).reduce((s, e) => s + e.amount, 0)
  })).filter(x => x.sum > 0)

  if (loading) return <div className="p-8">Loading...</div>
  if (error) return <div className="p-8 text-red-500">{error}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-2 text-gray-800">Expense Tracker</h1>
      <p className="text-2xl font-bold text-blue-600 mb-6">Total: ${total.toFixed(2)}</p>
      <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6 flex gap-3">
        <input className="flex-1 border border-gray-200 rounded px-3 py-2 text-sm" value={desc} onChange={e => setDesc(e.target.value)} placeholder="Description" />
        <input className="w-24 border border-gray-200 rounded px-3 py-2 text-sm" type="number" value={amount} onChange={e => setAmount(e.target.value)} placeholder="$0.00" />
        <select className="border border-gray-200 rounded px-2 py-2 text-sm" value={category} onChange={e => setCategory(e.target.value)}>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="bg-blue-500 text-white px-4 py-2 rounded text-sm hover:bg-blue-600" onClick={add}>Add</button>
      </div>
      {byCategory.length > 0 && (
        <div className="flex gap-2 flex-wrap mb-4">
          {byCategory.map(({ c, sum }) => (
            <span key={c} className="bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-xs font-medium">{c}: ${sum.toFixed(2)}</span>
          ))}
        </div>
      )}
      <ul className="space-y-2">
        {(expenses || []).map(e => (
          <li key={e.id} className="flex items-center gap-3 bg-white border border-gray-200 rounded px-4 py-3">
            <span className="flex-1 text-sm text-gray-700">{e.description}</span>
            <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{e.category}</span>
            <span className="text-sm font-medium text-gray-800">${e.amount.toFixed(2)}</span>
            <button className="text-red-400 hover:text-red-600 text-xs" onClick={() => remove(e.id)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
"""

# FS04: Bookmark manager
FS04_SERVER = """\
import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")

db.exec(`
  CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    tags TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`)

const app = express()
app.use(cors())
app.use(express.json())
app.get("/api/health", (req, res) => res.json({ ok: true }))

function crudRoutes(table) {
  const safe = table.replace(/[^a-z_]/gi, "")
  app.get(`/api/${safe}`, (req, res) => {
    try { res.json(db.prepare(`SELECT * FROM ${safe} ORDER BY created_at DESC`).all()) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.post(`/api/${safe}`, (req, res) => {
    try {
      const keys = Object.keys(req.body)
      const info = db.prepare(`INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`).run(...Object.values(req.body))
      res.json(db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(info.lastInsertRowid))
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.delete(`/api/${safe}/:id`, (req, res) => {
    try { db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id); res.json({ ok: true }) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
}

crudRoutes("bookmarks")
app.listen(PORT, () => console.log(`Server on :${PORT}`))
"""

FS04_APP = """\
import "./index.css"
import { useState } from "react"
import { useApi } from "./components/useApi"

interface Bookmark {
  id: number
  title: string
  url: string
  tags: string
}

export default function App() {
  const { data: bookmarks, loading, error, create, remove } = useApi<Bookmark>("bookmarks")
  const [title, setTitle] = useState("")
  const [url, setUrl] = useState("")
  const [tags, setTags] = useState("")
  const [search, setSearch] = useState("")

  const add = async () => {
    if (!title.trim() || !url.trim()) return
    await create({ title, url, tags })
    setTitle(""); setUrl(""); setTags("")
  }

  const filtered = (bookmarks || []).filter(b =>
    !search || b.title.toLowerCase().includes(search.toLowerCase()) || b.tags.includes(search.toLowerCase())
  )

  if (loading) return <div className="p-8">Loading...</div>
  if (error) return <div className="p-8 text-red-500">{error}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">Bookmarks</h1>
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4 space-y-2">
        <input className="w-full border border-gray-200 rounded px-3 py-2 text-sm" value={title} onChange={e => setTitle(e.target.value)} placeholder="Title" />
        <input className="w-full border border-gray-200 rounded px-3 py-2 text-sm" value={url} onChange={e => setUrl(e.target.value)} placeholder="URL (https://...)" />
        <div className="flex gap-2">
          <input className="flex-1 border border-gray-200 rounded px-3 py-2 text-sm" value={tags} onChange={e => setTags(e.target.value)} placeholder="tags (comma-separated)" />
          <button className="bg-blue-500 text-white px-4 py-2 rounded text-sm hover:bg-blue-600" onClick={add}>Save</button>
        </div>
      </div>
      <input className="w-full border border-gray-200 rounded px-3 py-2 text-sm mb-4 bg-white" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by title or tag..." />
      <ul className="space-y-2">
        {filtered.map(b => (
          <li key={b.id} className="bg-white border border-gray-200 rounded px-4 py-3 flex items-start gap-3">
            <div className="flex-1">
              <a href={b.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 font-medium text-sm hover:underline">{b.title}</a>
              <p className="text-xs text-gray-400 mt-0.5">{b.url}</p>
              {b.tags && <div className="flex gap-1 mt-1">{b.tags.split(",").map(t => t.trim()).filter(Boolean).map(t => <span key={t} className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded">{t}</span>)}</div>}
            </div>
            <button className="text-red-400 hover:text-red-600 text-xs mt-0.5" onClick={() => remove(b.id)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
"""

# FS05: Error recovery — missing useApi import → file_edit fix
FS05_BROKEN_APP = """\
import "./index.css"
import { useState, useEffect } from "react"

interface Contact {
  id: number
  name: string
  email: string
}

export default function App() {
  const [contacts, setContacts] = useState<Contact[]>([])

  useEffect(() => {
    fetch("/api/contacts").then(r => r.json()).then(setContacts)
  }, [])

  return (
    <div className="p-8">
      {contacts.map(c => <div key={c.id}>{c.name}</div>)}
    </div>
  )
}
"""

FS05_FIXED_APP = """\
import "./index.css"
import { useState } from "react"
import { useApi } from "./components/useApi"

interface Contact {
  id: number
  name: string
  email: string
  phone: string
}

export default function App() {
  const { data: contacts, loading, error, create, remove } = useApi<Contact>("contacts")
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [phone, setPhone] = useState("")

  const add = async () => {
    if (!name.trim()) return
    await create({ name, email, phone })
    setName(""); setEmail(""); setPhone("")
  }

  if (loading) return <div className="p-8">Loading...</div>
  if (error) return <div className="p-8 text-red-500">{error}</div>

  return (
    <div className="min-h-screen bg-gray-50 p-8 max-w-lg mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">Contacts</h1>
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6 space-y-2">
        <input className="w-full border border-gray-200 rounded px-3 py-2 text-sm" value={name} onChange={e => setName(e.target.value)} placeholder="Name" />
        <input className="w-full border border-gray-200 rounded px-3 py-2 text-sm" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" />
        <div className="flex gap-2">
          <input className="flex-1 border border-gray-200 rounded px-3 py-2 text-sm" value={phone} onChange={e => setPhone(e.target.value)} placeholder="Phone" />
          <button className="bg-blue-500 text-white px-4 py-2 rounded text-sm hover:bg-blue-600" onClick={add}>Add</button>
        </div>
      </div>
      <ul className="space-y-2">
        {(contacts || []).map(c => (
          <li key={c.id} className="bg-white border border-gray-200 rounded px-4 py-3 flex items-center gap-3">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-800">{c.name}</p>
              <p className="text-xs text-gray-500">{c.email} · {c.phone}</p>
            </div>
            <button className="text-red-400 hover:text-red-600 text-xs" onClick={() => remove(c.id)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
"""

FS05_SERVER = """\
import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")

db.exec(`
  CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`)

const app = express()
app.use(cors())
app.use(express.json())
app.get("/api/health", (req, res) => res.json({ ok: true }))

function crudRoutes(table) {
  const safe = table.replace(/[^a-z_]/gi, "")
  app.get(`/api/${safe}`, (req, res) => {
    try { res.json(db.prepare(`SELECT * FROM ${safe} ORDER BY name ASC`).all()) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.post(`/api/${safe}`, (req, res) => {
    try {
      const keys = Object.keys(req.body)
      const info = db.prepare(`INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`).run(...Object.values(req.body))
      res.json(db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(info.lastInsertRowid))
    } catch (e) { res.status(500).json({ error: e.message }) }
  })
  app.delete(`/api/${safe}/:id`, (req, res) => {
    try { db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id); res.json({ ok: true }) }
    catch (e) { res.status(500).json({ error: e.message }) }
  })
}

crudRoutes("contacts")
app.listen(PORT, () => console.log(`Server on :${PORT}`))
"""


def tc(id, name, args):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def tool_result(tool_call_id, content):
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def assistant_tc(id, name, args):
    return {"role": "assistant", "content": "", "tool_calls": [tc(id, name, args)]}


def tokenize(messages):
    return tokenizer.apply_chat_template(
        messages, tools=FS_TOOLS, tokenize=False, add_generation_prompt=False
    )


examples = []

# FS01: Persistent todo list
def build_fs01():
    return [
        {"role": "system", "content": FS_SYSTEM},
        {"role": "user", "content": "Build a persistent todo list app with a SQLite backend"},
        assistant_tc("c1", "project_init", {"name": "todo-app", "template": "fullstack"}),
        tool_result("c1", "[project_init] Created 'todo-app' from fullstack scaffold. Write server/index.js then src/App.tsx."),
        assistant_tc("c2", "file_write", {"path": "server/index.js", "content": FS01_SERVER}),
        tool_result("c2", "[file_write] server/index.js written."),
        assistant_tc("c3", "file_write", {"path": "src/App.tsx", "content": FS01_APP}),
        tool_result("c3", "[file_write] src/App.tsx written."),
        assistant_tc("c4", "shell_exec", {"command": "cd deliverables/todo-app && npm run build"}),
        tool_result("c4", "[shell_exec] Build succeeded. dist/ ready."),
        assistant_tc("c5", "undertow", {"path": "deliverables/todo-app/dist/index.html"}),
        tool_result("c5", "[undertow] PASS: page loads, inputs work, no console errors."),
        assistant_tc("c6", "message_result", {"text": "Your persistent todo list is ready. Tasks are saved to SQLite so they survive page reloads. Add tasks with Enter or the Add button, check them off, delete with the red ✕."}),
    ]

examples.append(tokenize(build_fs01()))

# FS02: Notes app with two-pane layout
def build_fs02():
    return [
        {"role": "system", "content": FS_SYSTEM},
        {"role": "user", "content": "Build a notes app with a sidebar list and editable note pane, saved to a database"},
        assistant_tc("c1", "project_init", {"name": "notes-app", "template": "fullstack"}),
        tool_result("c1", "[project_init] Created 'notes-app' from fullstack scaffold. Write server/index.js then src/App.tsx."),
        assistant_tc("c2", "file_write", {"path": "server/index.js", "content": FS02_SERVER}),
        tool_result("c2", "[file_write] server/index.js written."),
        assistant_tc("c3", "file_write", {"path": "src/App.tsx", "content": FS02_APP}),
        tool_result("c3", "[file_write] src/App.tsx written."),
        assistant_tc("c4", "shell_exec", {"command": "cd deliverables/notes-app && npm run build"}),
        tool_result("c4", "[shell_exec] Build succeeded. dist/ ready."),
        assistant_tc("c5", "undertow", {"path": "deliverables/notes-app/dist/index.html"}),
        tool_result("c5", "[undertow] PASS: sidebar renders, note content editable."),
        assistant_tc("c6", "message_result", {"text": "Notes app ready. Two-pane layout: sidebar shows all notes, right pane lets you edit title and content. Notes auto-save to SQLite with timestamps."}),
    ]

examples.append(tokenize(build_fs02()))

# FS03: Expense tracker with categories
def build_fs03():
    return [
        {"role": "system", "content": FS_SYSTEM},
        {"role": "user", "content": "Build an expense tracker with categories, totals, and SQLite persistence"},
        assistant_tc("c1", "project_init", {"name": "expense-tracker", "template": "fullstack"}),
        tool_result("c1", "[project_init] Created 'expense-tracker' from fullstack scaffold. Write server/index.js then src/App.tsx."),
        assistant_tc("c2", "file_write", {"path": "server/index.js", "content": FS03_SERVER}),
        tool_result("c2", "[file_write] server/index.js written."),
        assistant_tc("c3", "file_write", {"path": "src/App.tsx", "content": FS03_APP}),
        tool_result("c3", "[file_write] src/App.tsx written."),
        assistant_tc("c4", "shell_exec", {"command": "cd deliverables/expense-tracker && npm run build"}),
        tool_result("c4", "[shell_exec] Build succeeded. dist/ ready."),
        assistant_tc("c5", "undertow", {"path": "deliverables/expense-tracker/dist/index.html"}),
        tool_result("c5", "[undertow] PASS: page loads, expense list renders, total shown."),
        assistant_tc("c6", "message_result", {"text": "Expense tracker ready. Add expenses with description, amount, and category. Running total at top, category breakdown shown as tags. Data persists in SQLite."}),
    ]

examples.append(tokenize(build_fs03()))

# FS04: Bookmark manager with search
def build_fs04():
    return [
        {"role": "system", "content": FS_SYSTEM},
        {"role": "user", "content": "Build a bookmark manager with title, URL, tags, and live search"},
        assistant_tc("c1", "project_init", {"name": "bookmark-manager", "template": "fullstack"}),
        tool_result("c1", "[project_init] Created 'bookmark-manager' from fullstack scaffold. Write server/index.js then src/App.tsx."),
        assistant_tc("c2", "file_write", {"path": "server/index.js", "content": FS04_SERVER}),
        tool_result("c2", "[file_write] server/index.js written."),
        assistant_tc("c3", "file_write", {"path": "src/App.tsx", "content": FS04_APP}),
        tool_result("c3", "[file_write] src/App.tsx written."),
        assistant_tc("c4", "shell_exec", {"command": "cd deliverables/bookmark-manager && npm run build"}),
        tool_result("c4", "[shell_exec] Build succeeded. dist/ ready."),
        assistant_tc("c5", "undertow", {"path": "deliverables/bookmark-manager/dist/index.html"}),
        tool_result("c5", "[undertow] PASS: page loads, bookmark form visible, search input working."),
        assistant_tc("c6", "message_result", {"text": "Bookmark manager ready. Save bookmarks with title, URL, and comma-separated tags. Live search filters by title or tag. Bookmarks stored in SQLite."}),
    ]

examples.append(tokenize(build_fs04()))

# FS05: Error recovery — raw fetch() → should use useApi (TypeScript build error)
def build_fs05():
    return [
        {"role": "system", "content": FS_SYSTEM},
        {"role": "user", "content": "Build a contacts book with name, email, and phone, backed by a database"},
        assistant_tc("c1", "project_init", {"name": "contact-book", "template": "fullstack"}),
        tool_result("c1", "[project_init] Created 'contact-book' from fullstack scaffold. Write server/index.js then src/App.tsx."),
        assistant_tc("c2", "file_write", {"path": "server/index.js", "content": FS05_SERVER}),
        tool_result("c2", "[file_write] server/index.js written."),
        # Model mistakenly uses raw fetch, then gets an error, then fixes with useApi
        assistant_tc("c3", "file_write", {"path": "src/App.tsx", "content": FS05_BROKEN_APP}),
        tool_result("c3", "[file_write] src/App.tsx written."),
        assistant_tc("c4", "shell_exec", {"command": "cd deliverables/contact-book && npm run build"}),
        tool_result("c4", "[shell_exec] Error: src/App.tsx(9,9): TS2307: Cannot find module './components/useApi'. Also: raw fetch() detected — use useApi hook from ./components/useApi for data access."),
        assistant_tc("c5", "file_edit", {
            "path": "src/App.tsx",
            "old_text": FS05_BROKEN_APP,
            "new_text": FS05_FIXED_APP,
        }),
        tool_result("c5", "[file_edit] src/App.tsx updated."),
        assistant_tc("c6", "shell_exec", {"command": "cd deliverables/contact-book && npm run build"}),
        tool_result("c6", "[shell_exec] Build succeeded. dist/ ready."),
        assistant_tc("c7", "undertow", {"path": "deliverables/contact-book/dist/index.html"}),
        tool_result("c7", "[undertow] PASS: page loads, contact form renders."),
        assistant_tc("c8", "message_result", {"text": "Contact book ready. Add contacts with name, email, and phone. Sorted alphabetically by name. Data persists in SQLite."}),
    ]

examples.append(tokenize(build_fs05()))

# FS06: Short conversational (routing baseline)
def build_fs06():
    return [
        {"role": "system", "content": FS_SYSTEM},
        {"role": "user", "content": "What tables can I store in the SQLite backend?"},
        {"role": "assistant", "content": "Any table you need — the scaffold uses `crudRoutes(tableName)` in server/index.js to auto-generate GET/POST/PUT/DELETE endpoints. Just CREATE TABLE in the db.exec() block and call crudRoutes with the table name. Frontend accesses it via `useApi<YourType>(\"tablename\")` with no extra configuration.",
         "tool_calls": []},
    ]

examples.append(tokenize(build_fs06()))

# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
OUT_PATH = Path("workspace/training_data/fullstack_sft_v1.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_PATH, "w") as f:
    for ex in examples:
        f.write(json.dumps({"text": ex, "date": TODAY, "adapter": "fullstack-v1"}) + "\n")

print(f"\nWrote {len(examples)} examples to {OUT_PATH}")
print("Examples:")
for name in ["FS01 todo list", "FS02 notes two-pane", "FS03 expense tracker",
             "FS04 bookmark manager", "FS05 error recovery (fetch→useApi)",
             "FS06 conversational routing"]:
    print(f"  {name}")
print(f"\nTo train the fullstack adapter:")
print(f"  python training/train_unsloth.py \\")
print(f"    --model google/gemma-4-e4b-it \\")
print(f"    --data workspace/training_data/fullstack_sft_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-fullstack-v1 \\")
print(f"    --epochs 3 --lora-r 16 --lr 2e-4")
