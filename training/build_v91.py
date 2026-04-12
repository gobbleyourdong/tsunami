#!/usr/bin/env python3
"""build_v91.py -- v90 + 5 full trajectories for HF06/HF07/HF08.

Filling gaps in builder SFT that DPO v6 addresses at decision points
but full trajectories haven't yet been demonstrated:
  HF06: greeting -> message_chat (full conversational turn)
  HF07: dashboard scaffold -> App.tsx with proper component imports
  HF08: research then build (search_web once, use results, no re-search)
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import SYSTEM_TEXT, TOOLS

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/e4b_toolcall_train_v91.jsonl"


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


# ── HF06a: Greeting -> message_chat ──────────────────────────────────────────

def hf06_greeting():
    """Pure conversational turn: greeting -> message_chat, no tool exploration."""
    return [
        sys_msg(),
        u("Hello! What kinds of apps can you build?"),
        tc("message_chat",
           text=(
               "Hi! I can build quite a range of things:\n\n"
               "**Web apps**: React dashboards, todo lists, calculators, timers, games\n"
               "**Specialized**: Landing pages, data visualization (charts/graphs), form tools\n"
               "**Full-stack**: Apps with databases (Express + SQLite)\n"
               "**Real-time**: Chat apps, live dashboards (WebSocket)\n"
               "**Desktop**: Electron apps with native file access\n"
               "**Browser**: Chrome extensions\n"
               "**Games**: 2D/3D games with the Tsunami engine\n\n"
               "What would you like to build?"
           ),
           done=True),
        tr("message_chat", "Delivered."),
    ]


# ── HF06b: Help question then build (full trajectory) ────────────────────────

def hf06_help_then_build():
    """Question about capabilities, then follow-up build request."""
    return [
        sys_msg(),
        u("What's the difference between your fullstack and react-app scaffolds?"),
        tc("message_chat",
           text=(
               "**react-app**: Pure React frontend only. Great for UI-only tools, calculators, games. No server needed.\n\n"
               "**fullstack**: React frontend + Express + SQLite backend. Use this when you need to store data permanently, handle user accounts, or expose an API. Has `useApi()` hook for easy frontend-to-backend calls.\n\n"
               "Rule of thumb: if you need to save data between page refreshes, use fullstack."
           ),
           done=True),
        tr("message_chat", "Delivered."),
        u("Got it! Build me a reading list app — users can add books with title, author, status (to-read, reading, done)."),
        # -> fullstack (needs persistence)
        tc("project_init", name="reading-list", template="fullstack"),
        tr("project_init",
           "Scaffolded 'reading-list' (fullstack). Write server/index.js + src/App.tsx.\n\n"
           "## Fullstack Scaffold\n"
           "- server/index.js: Express + SQLite, uses useApi() hook\n"
           "- src/App.tsx: React frontend with useApi\n"
           "- crudRoutes(db, 'table') registers REST routes"),
        tc("file_write", path="deliverables/reading-list/server/index.js",
           content="""import express from "express"
import cors from "cors"
import Database from "better-sqlite3"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = process.env.PORT || 3001
const db = new Database(join(__dirname, "data.db"))
db.pragma("journal_mode = WAL")

db.exec(`
  CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT DEFAULT 'to-read',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`)

const app = express()
app.use(cors())
app.use(express.json())
app.get("/health", (req, res) => res.json({ ok: true }))

function crudRoutes(table) {
  const safe = table.replace(/[^a-z_]/gi, "")
  app.get(`/api/${safe}`, (req, res) => {
    res.json(db.prepare(`SELECT * FROM ${safe} ORDER BY created_at DESC`).all())
  })
  app.get(`/api/${safe}/:id`, (req, res) => {
    const row = db.prepare(`SELECT * FROM ${safe} WHERE id = ?`).get(req.params.id)
    row ? res.json(row) : res.status(404).json({ error: "not found" })
  })
  app.post(`/api/${safe}`, (req, res) => {
    const keys = Object.keys(req.body).filter(k => k !== "id")
    const vals = keys.map(k => req.body[k])
    const result = db.prepare(
      `INSERT INTO ${safe} (${keys.join(",")}) VALUES (${keys.map(() => "?").join(",")})`
    ).run(...vals)
    res.status(201).json({ id: result.lastInsertRowid })
  })
  app.put(`/api/${safe}/:id`, (req, res) => {
    const keys = Object.keys(req.body).filter(k => k !== "id")
    const vals = keys.map(k => req.body[k])
    db.prepare(
      `UPDATE ${safe} SET ${keys.map(k => `${k}=?`).join(",")}, updated_at=CURRENT_TIMESTAMP WHERE id=?`
    ).run(...vals, req.params.id)
    res.json({ ok: true })
  })
  app.delete(`/api/${safe}/:id`, (req, res) => {
    db.prepare(`DELETE FROM ${safe} WHERE id = ?`).run(req.params.id)
    res.json({ ok: true })
  })
}

crudRoutes("books")
app.listen(PORT, () => console.log(`Server: http://localhost:${PORT}`))
"""),
        tr("file_write", "Written: server/index.js"),
        tc("file_write", path="deliverables/reading-list/src/App.tsx",
           content="""import { useState } from 'react'
import { useApi } from './hooks/useApi'

interface Book { id?: number; title: string; author: string; status: 'to-read' | 'reading' | 'done' }

const STATUS_LABELS = { 'to-read': 'To Read', reading: 'Reading', done: 'Done' }
const STATUS_COLORS = { 'to-read': 'bg-gray-100 text-gray-700', reading: 'bg-blue-100 text-blue-700', done: 'bg-green-100 text-green-700' }

export default function App() {
  const { data: books, post, put, del, loading } = useApi<Book>('books')
  const [form, setForm] = useState<Omit<Book,'id'>>({ title: '', author: '', status: 'to-read' })
  const [filter, setFilter] = useState<string>('all')

  async function addBook(e: React.FormEvent) {
    e.preventDefault()
    if (!form.title.trim() || !form.author.trim()) return
    await post(form)
    setForm({ title: '', author: '', status: 'to-read' })
  }

  async function updateStatus(book: Book, status: Book['status']) {
    await put(book.id!, { ...book, status })
  }

  const filtered = filter === 'all' ? books : books.filter(b => b.status === filter)

  return (
    <div className="max-w-2xl mx-auto p-6 font-sans">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Reading List</h1>

      <form onSubmit={addBook} className="bg-white rounded-xl shadow-sm border p-4 mb-6">
        <div className="flex gap-3 mb-3">
          <input value={form.title} onChange={e=>setForm(f=>({...f,title:e.target.value}))}
            placeholder="Book title" className="flex-1 border rounded-lg p-2 text-sm" />
          <input value={form.author} onChange={e=>setForm(f=>({...f,author:e.target.value}))}
            placeholder="Author" className="flex-1 border rounded-lg p-2 text-sm" />
        </div>
        <div className="flex gap-3">
          <select value={form.status} onChange={e=>setForm(f=>({...f,status:e.target.value as Book['status']}))}
            className="border rounded-lg p-2 text-sm">
            {Object.entries(STATUS_LABELS).map(([v,l])=><option key={v} value={v}>{l}</option>)}
          </select>
          <button type="submit" className="flex-1 bg-indigo-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-indigo-700">
            Add Book
          </button>
        </div>
      </form>

      <div className="flex gap-2 mb-4">
        {['all',...Object.keys(STATUS_LABELS)].map(s=>(
          <button key={s} onClick={()=>setFilter(s)}
            className={`px-3 py-1 rounded-full text-sm font-medium ${filter===s?'bg-indigo-600 text-white':'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {s==='all'?'All':STATUS_LABELS[s as Book['status']]} ({s==='all'?books.length:books.filter(b=>b.status===s).length})
          </button>
        ))}
      </div>

      {loading && <p className="text-gray-400 text-center py-8">Loading...</p>}
      <div className="space-y-2">
        {filtered.map(book=>(
          <div key={book.id} className="bg-white rounded-xl border p-4 flex items-center gap-3">
            <div className="flex-1">
              <p className="font-medium text-gray-900">{book.title}</p>
              <p className="text-sm text-gray-500">{book.author}</p>
            </div>
            <select value={book.status}
              onChange={e=>updateStatus(book, e.target.value as Book['status'])}
              className="border rounded-lg px-2 py-1 text-sm">
              {Object.entries(STATUS_LABELS).map(([v,l])=><option key={v} value={v}>{l}</option>)}
            </select>
            <button onClick={()=>del(book.id!)} className="text-gray-400 hover:text-red-500 text-lg">×</button>
          </div>
        ))}
        {!loading && filtered.length === 0 && (
          <p className="text-center text-gray-400 py-8">No books yet. Add your first one!</p>
        )}
      </div>
    </div>
  )
}
"""),
        tr("file_write", "Written: src/App.tsx"),
        tc("shell_exec", command="cd deliverables/reading-list && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: Reading List app. Form: title input, author input, status dropdown, Add button. Filter tabs: All(0) To Read(0) Reading(0) Done(0). Empty state message below."),
        tc("message_result",
           text="Reading list app with fullstack persistence.\n\nFeatures:\n- Add books with title, author, and status\n- Filter by status (All / To Read / Reading / Done)\n- Change status from the list\n- Delete books\n- Data persists in SQLite (survives page refresh)"),
        tr("message_result", "Delivered."),
    ]


# ── HF07: Dashboard scaffold -> App.tsx with Layout+StatCard+ChartCard ────────

def hf07_dashboard_imports():
    """After dashboard scaffold, write App.tsx properly importing scaffold components."""
    return [
        sys_msg(),
        u("Build a SaaS metrics dashboard — monthly revenue, active users, churn rate, and a revenue trend chart."),
        # Dashboard signals -> dashboard template
        tc("project_init", name="saas-metrics", template="dashboard"),
        tr("project_init",
           "Scaffolded 'saas-metrics' (dashboard). Write src/App.tsx.\n\n"
           "## Dashboard Scaffold\n"
           "Pre-built: Layout (sidebar+topbar), StatCard (KPI tile), ChartCard (Recharts wrapper),\n"
           "DataTable (sortable), Modal, Toast, Badge, EmptyState.\n"
           "Import from './components/{Name}'. src/App.tsx is a stub."),
        # ← HF07: write App.tsx importing scaffold components properly
        tc("file_write", path="deliverables/saas-metrics/src/App.tsx",
           content="""import { Layout } from './components/Layout'
import { StatCard } from './components/StatCard'
import { ChartCard } from './components/ChartCard'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts'

const REVENUE_DATA = [
  { month: 'Nov', revenue: 42000 }, { month: 'Dec', revenue: 58000 },
  { month: 'Jan', revenue: 51000 }, { month: 'Feb', revenue: 67000 },
  { month: 'Mar', revenue: 72000 }, { month: 'Apr', revenue: 81000 },
]

const STATS = [
  { label: 'Monthly Revenue', value: '$81,240', change: '+12.4%', trend: 'up' as const },
  { label: 'Active Users',    value: '3,847',   change: '+8.2%',  trend: 'up' as const },
  { label: 'Churn Rate',      value: '2.1%',    change: '-0.3%',  trend: 'up' as const },
  { label: 'Avg Revenue/User', value: '$21.12', change: '+4.1%',  trend: 'up' as const },
]

export default function App() {
  return (
    <Layout title="SaaS Metrics" nav={[
      { label: 'Overview', href: '/', active: true },
      { label: 'Users', href: '/users' },
      { label: 'Revenue', href: '/revenue' },
    ]}>
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Overview</h1>

        <div className="grid grid-cols-4 gap-4 mb-6">
          {STATS.map(s => (
            <StatCard key={s.label} label={s.label} value={s.value}
              change={s.change} trend={s.trend} />
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ChartCard title="Revenue Trend (6 months)">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={REVENUE_DATA}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip formatter={v => [`$${v.toLocaleString()}`, 'Revenue']} />
                <Line type="monotone" dataKey="revenue" stroke="#6366f1" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Monthly Revenue (bar)">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={REVENUE_DATA}>
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip formatter={v => [`$${v.toLocaleString()}`, 'Revenue']} />
                <Bar dataKey="revenue" fill="#6366f1" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      </div>
    </Layout>
  )
}
"""),
        tr("file_write", "Written: src/App.tsx"),
        tc("shell_exec", command="cd deliverables/saas-metrics && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: Dashboard with sidebar nav. 4 KPI cards: Monthly Revenue $81,240 (+12.4%), Active Users 3,847 (+8.2%), Churn Rate 2.1%, Avg Revenue/User $21.12. Two charts side by side: line chart (revenue trend) and bar chart (monthly bars), both in indigo."),
        tc("message_result",
           text="SaaS metrics dashboard with:\n- 4 KPI stat cards: revenue, users, churn, ARPU\n- Line chart: 6-month revenue trend\n- Bar chart: monthly revenue breakdown\n- Sidebar navigation with Overview / Users / Revenue links"),
        tr("message_result", "Delivered."),
    ]


# ── HF08a: Research-then-build (no re-search) ─────────────────────────────────

def hf08_research_build():
    """Research 'like X' → search_web once → build using results (no repeat search)."""
    return [
        sys_msg(),
        u("Build a note-taking app inspired by Bear — markdown support, tags, sidebar with tag filtering."),
        # "inspired by Bear" = reference clone signal -> search first
        tc("search_web", query="Bear app design: tag sidebar, markdown notes, clean UI"),
        tr("search_web",
           "Bear app: clean sidebar listing all tags (clickable to filter), note list in middle column, markdown preview on right. Dark/light theme. Tags shown inline in notes with # prefix. Minimal chrome, focus on content. Main colors: warm gray sidebar, white note list, cream markdown area."),
        # Got results -> use them (no second search)
        tc("project_init", name="bear-notes"),
        tr("project_init", "Scaffolded 'bear-notes'. Write src/App.tsx."),
        tc("file_write", path="deliverables/bear-notes/src/App.tsx",
           content="""import { useState, useMemo } from 'react'

interface Note { id: number; title: string; body: string; tags: string[] }

const INITIAL: Note[] = [
  { id: 1, title: 'Welcome to Bear Notes', body: '# Welcome\\n\\nThis is your first note.\\n\\nUse **#tags** inline to organize.\\n\\n#welcome #getting-started', tags: ['welcome', 'getting-started'] },
  { id: 2, title: 'Project ideas', body: '## Ideas\\n\\n- Build a game\\n- Read a book\\n\\n#projects #personal', tags: ['projects', 'personal'] },
  { id: 3, title: 'Meeting notes', body: '## Q2 Planning\\n\\nAction items:\\n1. Ship dashboard\\n2. Write docs\\n\\n#work #meetings', tags: ['work', 'meetings'] },
]

function extractTags(body: string): string[] {
  return [...new Set((body.match(/#([a-z][a-z0-9-]*)/g) || []).map(t => t.slice(1)))]
}

function renderMd(body: string): string {
  return body
    .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mb-2">$1</h1>')
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-semibold mb-2 mt-4">$1</h2>')
    .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/^\\d+\\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
    .replace(/#([a-z][a-z0-9-]*)/g, '<span class="text-amber-600 font-medium">#$1</span>')
    .replace(/\\n/g, '<br/>')
}

export default function App() {
  const [notes, setNotes] = useState<Note[]>(INITIAL)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number>(1)
  const [editing, setEditing] = useState(false)

  const allTags = useMemo(() => {
    const tags = new Set<string>()
    notes.forEach(n => n.tags.forEach(t => tags.add(t)))
    return [...tags].sort()
  }, [notes])

  const filtered = selectedTag ? notes.filter(n => n.tags.includes(selectedTag)) : notes
  const selected = notes.find(n => n.id === selectedId)

  function updateNote(id: number, body: string) {
    setNotes(ns => ns.map(n => n.id===id ? { ...n, body, tags: extractTags(body) } : n))
  }

  function newNote() {
    const id = Date.now()
    const note: Note = { id, title: 'New note', body: '# New note\\n\\n', tags: [] }
    setNotes(ns => [note, ...ns])
    setSelectedId(id)
    setEditing(true)
  }

  return (
    <div className="flex h-screen bg-gray-50 font-sans text-sm">
      {/* Tag sidebar */}
      <div className="w-48 bg-gray-900 text-gray-300 flex flex-col">
        <div className="p-3 border-b border-gray-700 font-semibold text-white">Bear Notes</div>
        <div className="flex-1 overflow-y-auto p-2">
          <button onClick={() => setSelectedTag(null)}
            className={`w-full text-left px-3 py-1.5 rounded-lg mb-1 ${!selectedTag ? 'bg-amber-500 text-white' : 'hover:bg-gray-700'}`}>
            All Notes ({notes.length})
          </button>
          {allTags.map(tag => (
            <button key={tag} onClick={() => setSelectedTag(tag)}
              className={`w-full text-left px-3 py-1.5 rounded-lg mb-1 ${selectedTag===tag ? 'bg-amber-500 text-white' : 'hover:bg-gray-700'}`}>
              #{tag}
            </button>
          ))}
        </div>
        <button onClick={newNote} className="p-3 text-amber-400 hover:text-amber-300 border-t border-gray-700 text-left">
          + New Note
        </button>
      </div>

      {/* Note list */}
      <div className="w-56 bg-white border-r overflow-y-auto">
        {filtered.map(note => (
          <div key={note.id} onClick={() => { setSelectedId(note.id); setEditing(false) }}
            className={`p-3 border-b cursor-pointer hover:bg-gray-50 ${selectedId===note.id ? 'bg-amber-50 border-l-2 border-l-amber-500' : ''}`}>
            <p className="font-medium text-gray-900 truncate">{note.title}</p>
            <p className="text-xs text-gray-400 mt-0.5 truncate">{note.body.slice(0,50)}...</p>
          </div>
        ))}
      </div>

      {/* Editor / Preview */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 border-b bg-white">
          <button onClick={() => setEditing(e => !e)}
            className="text-xs px-3 py-1 rounded bg-gray-100 hover:bg-gray-200">
            {editing ? 'Preview' : 'Edit'}
          </button>
        </div>
        {selected && editing ? (
          <textarea className="flex-1 p-6 font-mono text-sm bg-cream resize-none outline-none"
            value={selected.body}
            onChange={e => updateNote(selected.id, e.target.value)} />
        ) : selected ? (
          <div className="flex-1 p-6 overflow-y-auto prose max-w-none"
            dangerouslySetInnerHTML={{ __html: renderMd(selected.body) }} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">Select a note</div>
        )}
      </div>
    </div>
  )
}
"""),
        tr("file_write", "Written: src/App.tsx"),
        tc("shell_exec", command="cd deliverables/bear-notes && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: 3-column layout. Dark gray sidebar with tag list: All Notes (3), #getting-started, #meetings, #personal, #projects, #welcome. Middle column: 3 note titles. Right column: markdown preview of selected note with heading and formatted body. Amber accent color throughout."),
        tc("message_result",
           text="Bear-inspired note app:\n- Dark sidebar with tag navigation (all notes or filter by tag)\n- Note list (title + preview)\n- Markdown editor/preview toggle\n- Tags: use #tag-name inline in note body, auto-extracted\n\nClick 'Edit' to write markdown, 'Preview' to render it. + New Note at bottom of sidebar."),
        tr("message_result", "Delivered."),
    ]


# ── HF08b: API research then build ────────────────────────────────────────────

def hf08_api_research():
    """Research an API, then use it to build (no re-search after finding results)."""
    return [
        sys_msg(),
        u("Build a cryptocurrency price tracker. Find a free API first."),
        # Research first (API needed) -> search_web
        tc("search_web", query="free cryptocurrency price API no key required CORS 2026"),
        tr("search_web",
           "Results: 1. CoinGecko API — free, no key, CORS friendly, endpoint: https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd. 2. CryptoCompare — free tier, needs key. Best: CoinGecko (no key, no CORS issues)."),
        # Got CoinGecko URL -> build immediately (no second search)
        tc("project_init", name="crypto-tracker"),
        tr("project_init", "Scaffolded 'crypto-tracker'. Write src/App.tsx."),
        tc("file_write", path="deliverables/crypto-tracker/src/App.tsx",
           content="""import { useState, useEffect, useCallback } from 'react'

const COINS = ['bitcoin', 'ethereum', 'solana', 'dogecoin', 'chainlink']

interface Price { usd: number; usd_24h_change: number }
type Prices = Record<string, Price>

const ICONS: Record<string, string> = {
  bitcoin: '₿', ethereum: 'Ξ', solana: '◎', dogecoin: 'Ð', chainlink: '⬡'
}

export default function App() {
  const [prices, setPrices] = useState<Prices>({})
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchPrices = useCallback(async () => {
    try {
      const res = await fetch(
        `https://api.coingecko.com/api/v3/simple/price?ids=${COINS.join(',')}&vs_currencies=usd&include_24hr_change=true`
      )
      const data = await res.json()
      setPrices(data)
      setLastUpdated(new Date())
    } catch (e) {
      console.error('Price fetch failed:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPrices()
    const interval = setInterval(fetchPrices, 30000)  // refresh every 30s
    return () => clearInterval(interval)
  }, [fetchPrices])

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-lg mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Crypto Tracker</h1>
          <div className="text-right">
            <button onClick={fetchPrices} className="px-3 py-1 bg-gray-700 rounded-lg text-sm hover:bg-gray-600">
              Refresh
            </button>
            {lastUpdated && (
              <p className="text-xs text-gray-500 mt-1">
                Updated {lastUpdated.toLocaleTimeString()}
              </p>
            )}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-16 text-gray-400">Loading prices...</div>
        ) : (
          <div className="space-y-3">
            {COINS.map(coin => {
              const p = prices[coin]
              if (!p) return null
              const change = p.usd_24h_change
              const up = change >= 0
              return (
                <div key={coin} className="bg-gray-800 rounded-xl p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{ICONS[coin]}</span>
                    <span className="font-medium capitalize">{coin}</span>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-lg">${p.usd.toLocaleString()}</p>
                    <p className={`text-sm font-medium ${up ? 'text-green-400' : 'text-red-400'}`}>
                      {up ? '+' : ''}{change.toFixed(2)}% 24h
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
        <p className="text-center text-xs text-gray-600 mt-4">Powered by CoinGecko. Auto-refreshes every 30s.</p>
      </div>
    </div>
  )
}
"""),
        tr("file_write", "Written: src/App.tsx"),
        tc("shell_exec", command="cd deliverables/crypto-tracker && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: Dark background, Crypto Tracker heading. 5 coin cards: Bitcoin ₿ $62,340 +2.1%, Ethereum Ξ $3,102 -0.4%, Solana +5.2%, Dogecoin, Chainlink. Green up arrows, red down arrows. Refresh button top right."),
        tc("message_result",
           text="Crypto price tracker using CoinGecko API (free, no key needed).\n\nFeatures:\n- 5 coins: Bitcoin, Ethereum, Solana, Dogecoin, Chainlink\n- Real-time prices in USD with 24h % change\n- Auto-refreshes every 30 seconds\n- Manual refresh button\n- Color-coded: green=up, red=down"),
        tr("message_result", "Delivered."),
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    # Load v90 examples
    v90_path = "workspace/training_data/e4b_toolcall_train_v90.jsonl"
    v90 = []
    if os.path.exists(v90_path):
        with open(v90_path) as f:
            v90 = [json.loads(l) for l in f if l.strip()]
    print(f"Loaded {len(v90)} from v90")

    new_fns = [
        hf06_greeting,
        hf06_help_then_build,
        hf07_dashboard_imports,
        hf08_research_build,
        hf08_api_research,
    ]
    new_examples = []
    for fn in new_fns:
        msgs = fn()
        text = tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        if not isinstance(text, str):
            text = tok.decode(text)
        new_examples.append({"text": text, "source": fn.__name__})
        print(f"  {fn.__name__}: {len(msgs)} msgs -> {len(text)} chars")

    all_examples = v90 + new_examples
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in all_examples:
            f.write(json.dumps(ex) + "\n")

    print(f"\nTotal: {len(all_examples)} ({len(v90)} v90 + {len(new_examples)} new)")
    print(f"Wrote to {OUT_PATH}")


if __name__ == "__main__":
    main()
