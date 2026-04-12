#!/usr/bin/env python3
"""build_v93.py — SFT v93 for build-v89/90/91/92 adapter.

Loads v92 (54 examples), adds 4 new examples = 58 total.
New patterns:
  - Drag-and-drop kanban (HTML5 DnD API, no library)
  - Infinite scroll with IntersectionObserver
  - Markdown editor with live preview (marked.js + useDebounce)
  - CSS custom properties theme picker (useTheme hook + localStorage)
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.build_v69 import SYSTEM_TEXT, TOOLS

V92 = Path("workspace/training_data/e4b_toolcall_train_v92.jsonl")
OUT = Path("workspace/training_data/e4b_toolcall_train_v93.jsonl")


def tc(tool_name, **kw):
    return {"role": "tool_call", "content": json.dumps({"name": tool_name, "parameters": kw})}


def tr(content):
    return {"role": "tool_result", "content": content}


# ── dd01: Drag-and-drop Kanban (HTML5 DnD, no library) ──────────────────────

def dd01_kanban():
    return [
        {"role": "user", "content": "Build a kanban board with drag-and-drop between columns (Todo, In Progress, Done). No external library — use the HTML5 drag-and-drop API."},
        tc("project_init", name="kanban-board"),
        tr("Project 'kanban-board' created. Dev server: http://localhost:9876"),
        tc("file_write", path="workspace/deliverables/kanban-board/src/App.tsx",
           content="""import { useState, DragEvent } from 'react'

interface Card { id: string; title: string; desc: string }
type Column = 'todo' | 'doing' | 'done'
interface Board { todo: Card[]; doing: Card[]; done: Card[] }

const INIT: Board = {
  todo: [
    { id: '1', title: 'Design mockups', desc: 'Create Figma designs for v2' },
    { id: '2', title: 'Write tests', desc: 'Unit + integration coverage' },
    { id: '3', title: 'Update docs', desc: 'README and API reference' },
  ],
  doing: [
    { id: '4', title: 'Implement auth', desc: 'JWT login flow' },
    { id: '5', title: 'Fix bug #142', desc: 'Race condition in upload' },
  ],
  done: [
    { id: '6', title: 'Project setup', desc: 'Vite + TS scaffold' },
  ],
}

const COL_LABELS: Record<Column, string> = {
  todo: '📋 To Do', doing: '⚡ In Progress', done: '✅ Done'
}
const COL_COLORS: Record<Column, string> = {
  todo: '#3b82f6', doing: '#f59e0b', done: '#22c55e'
}

export default function App() {
  const [board, setBoard] = useState<Board>(INIT)
  const [dragging, setDragging] = useState<string | null>(null)
  const [over, setOver]     = useState<Column | null>(null)
  const [newTitle, setNewTitle] = useState('')

  function onDragStart(e: DragEvent, cardId: string) {
    e.dataTransfer.setData('text/plain', cardId)
    setDragging(cardId)
  }

  function onDragOver(e: DragEvent, col: Column) {
    e.preventDefault()  // required to allow drop
    setOver(col)
  }

  function onDrop(e: DragEvent, target: Column) {
    e.preventDefault()
    const cardId = e.dataTransfer.getData('text/plain')
    setBoard(prev => {
      const next: Board = { todo: [...prev.todo], doing: [...prev.doing], done: [...prev.done] }
      for (const col of ['todo', 'doing', 'done'] as Column[]) {
        const idx = next[col].findIndex(c => c.id === cardId)
        if (idx !== -1) {
          const [card] = next[col].splice(idx, 1)
          next[target].unshift(card)
          break
        }
      }
      return next
    })
    setDragging(null); setOver(null)
  }

  function addCard() {
    const title = newTitle.trim()
    if (!title) return
    const card: Card = { id: Date.now().toString(), title, desc: '' }
    setBoard(prev => ({ ...prev, todo: [card, ...prev.todo] }))
    setNewTitle('')
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', padding: '24px', fontFamily: 'system-ui,sans-serif' }}>
      <h1 style={{ color: '#f8fafc', margin: '0 0 8px', fontSize: 24 }}>Kanban Board</h1>

      {/* Add card */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <input value={newTitle} onChange={e => setNewTitle(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addCard()}
          placeholder="New card title…"
          style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: '1px solid #334155', background: '#1e293b', color: '#f1f5f9', fontSize: 14 }} />
        <button onClick={addCard}
          style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: '#3b82f6', color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
          Add
        </button>
      </div>

      {/* Columns */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {(['todo','doing','done'] as Column[]).map(col => (
          <div key={col}
            onDragOver={e => onDragOver(e, col)}
            onDrop={e => onDrop(e, col)}
            onDragLeave={() => setOver(null)}
            style={{
              background: over === col ? '#1e3a5f' : '#1e293b',
              borderRadius: 12, padding: 16, minHeight: 300,
              border: `2px dashed ${over === col ? COL_COLORS[col] : 'transparent'}`,
              transition: 'all 0.15s',
            }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: COL_COLORS[col] }} />
              <span style={{ color: '#94a3b8', fontWeight: 700, fontSize: 14 }}>{COL_LABELS[col]}</span>
              <span style={{ marginLeft: 'auto', background: '#334155', borderRadius: 12, padding: '2px 8px', fontSize: 12, color: '#64748b' }}>
                {board[col].length}
              </span>
            </div>
            {board[col].map(card => (
              <div key={card.id}
                draggable
                onDragStart={e => onDragStart(e, card.id)}
                style={{
                  background: dragging === card.id ? '#0f172a' : '#0f172a',
                  border: '1px solid #334155', borderRadius: 8, padding: '10px 12px',
                  marginBottom: 8, cursor: 'grab', opacity: dragging === card.id ? 0.4 : 1,
                  transition: 'opacity 0.15s',
                }}>
                <div style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{card.title}</div>
                {card.desc && <div style={{ color: '#64748b', fontSize: 12 }}>{card.desc}</div>}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
"""),
        tr("Written: src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/kanban-board && npm run build 2>&1 | tail -5"),
        tr("✓ built in 0.9s"),
        tc("undertow"),
        tr("Screenshot: dark kanban board — three columns (To Do / In Progress / Done) with colored dot headers and card counts. Cards have title + description. Add card input at top. Drop zone highlight visible on drag."),
        tc("message_result", text="**Kanban Board** built with HTML5 DnD API — no library needed.\n\n`onDragStart` → `setData('text/plain', id)` / `onDragOver` → `preventDefault()` (required to allow drop) / `onDrop` → reads id, splices card between columns. Visual drop-zone highlight on drag-over. Add cards via the input at top.", done=True),
        tr("Message sent"),
    ]


# ── inf01: Infinite Scroll feed with IntersectionObserver ───────────────────

def inf01_infinite_scroll():
    return [
        {"role": "user", "content": "Build a blog post feed with infinite scroll. Load 10 posts at a time; when the user scrolls to the bottom, automatically load the next page. Use IntersectionObserver, not scroll events."},
        tc("project_init", name="infinite-feed"),
        tr("Project 'infinite-feed' created. Dev server: http://localhost:9876"),
        tc("file_write", path="workspace/deliverables/infinite-feed/src/App.tsx",
           content="""import { useState, useEffect, useRef, useCallback } from 'react'

// Mock post generator — replace with real API in production
function generatePosts(page: number, perPage = 10) {
  return Array.from({ length: perPage }, (_, i) => {
    const n = (page - 1) * perPage + i + 1
    return {
      id: n,
      title: `Post ${n}: ${['Building with React', 'TypeScript Tips', 'CSS Grid Deep Dive', 'Performance Patterns', 'Testing Strategy'][n % 5]}`,
      excerpt: `This is the excerpt for post ${n}. It summarizes the article content in a few sentences to give the reader a preview before they click through.`,
      author: ['Alice Chen', 'Bob Smith', 'Carol White', 'Dan Lee'][n % 4],
      date: new Date(Date.now() - n * 86400000).toLocaleDateString(),
      readTime: 2 + (n % 8),
      tag: ['React', 'TypeScript', 'CSS', 'Performance', 'Testing'][n % 5],
    }
  })
}

interface Post { id: number; title: string; excerpt: string; author: string; date: string; readTime: number; tag: string }

export default function App() {
  const [posts, setPosts]     = useState<Post[]>([])
  const [page, setPage]       = useState(1)
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const sentinelRef           = useRef<HTMLDivElement>(null)

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return
    setLoading(true)
    // Simulate network delay
    await new Promise(r => setTimeout(r, 600))
    const next = generatePosts(page)
    if (next.length < 10 || page >= 5) {  // 5 pages = 50 posts max
      setHasMore(false)
    }
    setPosts(prev => [...prev, ...next])
    setPage(p => p + 1)
    setLoading(false)
  }, [page, loading, hasMore])

  // Initial load
  useEffect(() => { loadMore() }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // IntersectionObserver watches the sentinel div at the bottom
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      entries => { if (entries[0].isIntersecting && !loading) loadMore() },
      { rootMargin: '200px' }  // trigger 200px before sentinel hits viewport
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadMore, loading])

  const TAG_COLORS: Record<string, string> = {
    React: '#61dafb', TypeScript: '#3178c6', CSS: '#f472b6',
    Performance: '#fb923c', Testing: '#4ade80',
  }

  return (
    <div style={{ maxWidth: 680, margin: '0 auto', padding: '24px 16px', fontFamily: 'system-ui,sans-serif', background: '#0f172a', minHeight: '100vh' }}>
      <h1 style={{ color: '#f8fafc', fontSize: 28, fontWeight: 800, marginBottom: 8 }}>Dev Blog</h1>
      <p style={{ color: '#64748b', marginBottom: 32 }}>{posts.length} posts loaded</p>

      {posts.map(post => (
        <article key={post.id} style={{
          background: '#1e293b', borderRadius: 12, padding: '20px 24px',
          marginBottom: 16, border: '1px solid #334155',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{
              background: TAG_COLORS[post.tag] + '20', color: TAG_COLORS[post.tag],
              padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 600,
            }}>{post.tag}</span>
            <span style={{ color: '#475569', fontSize: 12 }}>{post.readTime} min read</span>
          </div>
          <h2 style={{ color: '#f1f5f9', fontSize: 18, fontWeight: 700, margin: '0 0 8px', lineHeight: 1.3 }}>{post.title}</h2>
          <p style={{ color: '#94a3b8', fontSize: 14, margin: '0 0 12px', lineHeight: 1.6 }}>{post.excerpt}</p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#334155', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: 12 }}>
              {post.author[0]}
            </div>
            <span style={{ color: '#64748b', fontSize: 13 }}>{post.author} · {post.date}</span>
          </div>
        </article>
      ))}

      {/* Sentinel: IntersectionObserver target */}
      <div ref={sentinelRef} style={{ height: 1 }} />

      {loading && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: '#64748b' }}>
          <div style={{ display: 'inline-block', width: 24, height: 24, border: '3px solid #334155', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
        </div>
      )}

      {!hasMore && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: '#475569', fontSize: 14 }}>
          You've reached the end · {posts.length} posts
        </div>
      )}
    </div>
  )
}
"""),
        tr("Written: src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/infinite-feed && npm run build 2>&1 | tail -5"),
        tr("✓ built in 0.9s"),
        tc("undertow"),
        tr("Screenshot: dark blog feed, cards with colored tags (React/TypeScript/CSS), author avatars, post count '10 posts loaded'. Bottom of visible area has a subtle loading spinner."),
        tc("message_result", text="**Infinite Feed** built with IntersectionObserver.\n\nKey pattern: `sentinelRef` div at end of list → `observer.observe(sentinel)` fires `loadMore()` when 200px from viewport edge (`rootMargin: '200px'`). No scroll events. Cleans up with `observer.disconnect()` on unmount. Replace `generatePosts()` with a real API call.", done=True),
        tr("Message sent"),
    ]


# ── md01: Markdown editor with live preview ──────────────────────────────────

def md01_markdown_editor():
    return [
        {"role": "user", "content": "Build a markdown editor with a live preview pane. Left side is textarea for writing, right side shows the rendered HTML. Add debouncing so the preview doesn't re-render on every keystroke."},
        tc("project_init", name="markdown-editor", dependencies=["marked"]),
        tr("Project 'markdown-editor' created (extra deps: marked). Dev server: http://localhost:9876"),
        tc("file_write", path="workspace/deliverables/markdown-editor/src/App.tsx",
           content="""import { useState, useEffect, useCallback } from 'react'
import { marked } from 'marked'

// Configure marked for safe rendering
marked.setOptions({ gfm: true, breaks: true })

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

const STARTER = `# Hello, Markdown!

Write **bold**, *italic*, or \`inline code\`.

## Features
- Live preview (debounced 300ms)
- GitHub Flavored Markdown
- Code blocks

\`\`\`typescript
const greeting = (name: string) => \`Hello, \${name}!\`
\`\`\`

> Blockquote text looks like this.

---

[Link example](https://example.com)
`

export default function App() {
  const [source, setSource]   = useState(STARTER)
  const [wordCount, setWC]    = useState(0)
  const debouncedSrc          = useDebounce(source, 300)
  const [html, setHtml]       = useState('')
  const [copied, setCopied]   = useState(false)

  useEffect(() => {
    setHtml(marked(debouncedSrc) as string)
    setWC(debouncedSrc.trim().split(/\s+/).filter(Boolean).length)
  }, [debouncedSrc])

  const copyMarkdown = useCallback(() => {
    navigator.clipboard.writeText(source)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [source])

  const clearAll = useCallback(() => {
    if (confirm('Clear all content?')) setSource('')
  }, [])

  const S = {
    app: { display: 'flex', flexDirection: 'column' as const, height: '100vh', background: '#0f172a', fontFamily: 'system-ui,sans-serif' },
    toolbar: { display: 'flex', alignItems: 'center', gap: 12, padding: '8px 16px', background: '#1e293b', borderBottom: '1px solid #334155' },
    title: { color: '#f1f5f9', fontWeight: 700, fontSize: 16, marginRight: 'auto' },
    btn: { padding: '5px 12px', borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#94a3b8', cursor: 'pointer', fontSize: 13 },
    panes: { display: 'grid', gridTemplateColumns: '1fr 1fr', flex: 1, overflow: 'hidden' },
    textarea: { width: '100%', height: '100%', background: '#0f172a', color: '#e2e8f0', border: 'none', borderRight: '1px solid #334155', padding: '20px', fontSize: 14, fontFamily: 'ui-monospace, monospace', lineHeight: 1.7, resize: 'none' as const, outline: 'none', boxSizing: 'border-box' as const },
    preview: { height: '100%', overflow: 'auto', padding: '20px 24px', color: '#e2e8f0', fontSize: 15, lineHeight: 1.7 },
    status: { padding: '6px 16px', background: '#1e293b', borderTop: '1px solid #334155', display: 'flex', gap: 16, fontSize: 12, color: '#64748b' },
  }

  return (
    <div style={S.app}>
      <div style={S.toolbar}>
        <span style={S.title}>Markdown Editor</span>
        <button style={S.btn} onClick={copyMarkdown}>{copied ? '✓ Copied' : 'Copy MD'}</button>
        <button style={S.btn} onClick={clearAll}>Clear</button>
      </div>

      <div style={S.panes}>
        <textarea
          style={S.textarea}
          value={source}
          onChange={e => setSource(e.target.value)}
          placeholder="Write markdown here…"
          spellCheck={false}
        />
        <div style={S.preview}>
          <style>{`
            .md-preview h1,h2,h3{color:#f1f5f9;border-bottom:1px solid #334155;padding-bottom:6px}
            .md-preview code{background:#1e293b;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:13px;color:#7dd3fc}
            .md-preview pre{background:#1e293b;padding:16px;border-radius:8px;overflow:auto}
            .md-preview pre code{background:none;padding:0;color:#e2e8f0}
            .md-preview blockquote{border-left:4px solid #3b82f6;margin:0;padding-left:16px;color:#94a3b8}
            .md-preview a{color:#60a5fa}
            .md-preview ul,ol{padding-left:20px}
            .md-preview hr{border-color:#334155}
          `}</style>
          <div className="md-preview" dangerouslySetInnerHTML={{ __html: html }} />
        </div>
      </div>

      <div style={S.status}>
        <span>{source.length} chars</span>
        <span>{wordCount} words</span>
        <span>{source.split('\\n').length} lines</span>
        <span style={{ marginLeft: 'auto' }}>Preview debounced 300ms</span>
      </div>
    </div>
  )
}
"""),
        tr("Written: src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/markdown-editor && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.1s"),
        tc("undertow"),
        tr("Screenshot: split-pane editor — left: monospace textarea with markdown source, right: rendered HTML preview with heading styles, code block, blockquote. Status bar at bottom shows char/word/line count."),
        tc("message_result", text="**Markdown Editor** built with `marked` + `useDebounce(300ms)`.\n\nPattern: `source` state → `useDebounce(source, 300)` → `useEffect(() => setHtml(marked(debouncedSrc)))`. Split-pane layout with CSS Grid. Status bar: chars / words / lines.", done=True),
        tr("Message sent"),
    ]


# ── vc01: CSS custom properties theme picker ─────────────────────────────────

def vc01_theme_picker():
    return [
        {"role": "user", "content": "Build a color theme picker app. The app itself demonstrates the theme — it has a header, cards, and buttons that all change when you pick a theme. Themes should persist across page reloads. Support at least 5 preset themes plus a custom color picker."},
        tc("project_init", name="theme-picker"),
        tr("Project 'theme-picker' created. Dev server: http://localhost:9876"),
        tc("file_write", path="workspace/deliverables/theme-picker/src/App.tsx",
           content="""import { useState, useEffect, createContext, useContext, ReactNode } from 'react'

interface Theme {
  name: string; primary: string; secondary: string; bg: string; surface: string; text: string; muted: string
}

const PRESETS: Theme[] = [
  { name: 'Ocean',    primary:'#0ea5e9', secondary:'#06b6d4', bg:'#0f172a', surface:'#1e293b', text:'#f1f5f9', muted:'#64748b' },
  { name: 'Forest',  primary:'#22c55e', secondary:'#16a34a', bg:'#052e16', surface:'#14532d', text:'#dcfce7', muted:'#4ade80' },
  { name: 'Sunset',  primary:'#f97316', secondary:'#ef4444', bg:'#1c0a00', surface:'#431407', text:'#fff7ed', muted:'#fb923c' },
  { name: 'Purple',  primary:'#a855f7', secondary:'#7c3aed', bg:'#0f0a1e', surface:'#1e1035', text:'#faf5ff', muted:'#c084fc' },
  { name: 'Rose',    primary:'#f43f5e', secondary:'#e11d48', bg:'#1c0714', surface:'#3b0764', text:'#fff1f2', muted:'#fb7185' },
  { name: 'Neutral', primary:'#94a3b8', secondary:'#64748b', bg:'#0f172a', surface:'#1e293b', text:'#f8fafc', muted:'#475569' },
]

// Apply theme to CSS custom properties on :root
function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.style.setProperty('--color-primary',   theme.primary)
  root.style.setProperty('--color-secondary', theme.secondary)
  root.style.setProperty('--color-bg',        theme.bg)
  root.style.setProperty('--color-surface',   theme.surface)
  root.style.setProperty('--color-text',      theme.text)
  root.style.setProperty('--color-muted',     theme.muted)
}

interface ThemeCtx { theme: Theme; setTheme: (t: Theme) => void }
const ThemeContext = createContext<ThemeCtx>({ theme: PRESETS[0], setTheme: () => {} })

function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    try {
      const saved = localStorage.getItem('app_theme')
      return saved ? (JSON.parse(saved) as Theme) : PRESETS[0]
    } catch { return PRESETS[0] }
  })

  function setTheme(t: Theme) {
    setThemeState(t)
    applyTheme(t)
    localStorage.setItem('app_theme', JSON.stringify(t))
  }

  useEffect(() => { applyTheme(theme) }, [])  // Apply on mount

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
}

function useTheme() { return useContext(ThemeContext) }

// ---- UI Components using CSS vars ----

function Header() {
  const { theme } = useTheme()
  return (
    <header style={{ background: 'var(--color-surface)', borderBottom: '1px solid var(--color-primary)33', padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--color-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800 }}>T</div>
      <span style={{ color: 'var(--color-text)', fontWeight: 700, fontSize: 18 }}>ThemeApp</span>
      <span style={{ marginLeft: 'auto', background: 'var(--color-primary)22', color: 'var(--color-primary)', padding: '4px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600 }}>{theme.name}</span>
    </header>
  )
}

function DemoCard({ title, desc }: { title: string; desc: string }) {
  return (
    <div style={{ background: 'var(--color-surface)', borderRadius: 12, padding: '16px 20px', border: '1px solid var(--color-primary)33' }}>
      <h3 style={{ color: 'var(--color-text)', margin: '0 0 6px', fontSize: 16 }}>{title}</h3>
      <p style={{ color: 'var(--color-muted)', margin: 0, fontSize: 14, lineHeight: 1.5 }}>{desc}</p>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button style={{ padding: '6px 14px', borderRadius: 6, border: 'none', background: 'var(--color-primary)', color: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>Primary</button>
        <button style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid var(--color-primary)', background: 'transparent', color: 'var(--color-primary)', cursor: 'pointer', fontSize: 13 }}>Outline</button>
      </div>
    </div>
  )
}

function ThemePicker() {
  const { theme, setTheme } = useTheme()
  const [custom, setCustom] = useState(theme.primary)

  function applyCustom() {
    setTheme({ name: 'Custom', primary: custom, secondary: custom, bg: '#0f172a', surface: '#1e293b', text: '#f1f5f9', muted: '#64748b' })
  }

  return (
    <div style={{ background: 'var(--color-surface)', borderRadius: 16, padding: '20px 24px', marginBottom: 24 }}>
      <h2 style={{ color: 'var(--color-text)', margin: '0 0 16px', fontSize: 18 }}>Choose Theme</h2>
      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 10, marginBottom: 16 }}>
        {PRESETS.map(t => (
          <button key={t.name} onClick={() => setTheme(t)} style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', borderRadius: 8,
            border: `2px solid ${theme.name === t.name ? t.primary : 'transparent'}`,
            background: theme.name === t.name ? t.primary + '22' : '#0f172a',
            cursor: 'pointer', color: 'var(--color-text)', fontSize: 14, fontWeight: 500,
          }}>
            <div style={{ width: 16, height: 16, borderRadius: '50%', background: t.primary }} />
            {t.name}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <label style={{ color: 'var(--color-muted)', fontSize: 14 }}>Custom color:</label>
        <input type="color" value={custom} onChange={e => setCustom(e.target.value)}
          style={{ width: 40, height: 32, border: 'none', borderRadius: 6, cursor: 'pointer', background: 'none' }} />
        <button onClick={applyCustom}
          style={{ padding: '6px 14px', borderRadius: 6, border: 'none', background: 'var(--color-primary)', color: '#fff', cursor: 'pointer', fontSize: 13 }}>
          Apply
        </button>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <div style={{ minHeight: '100vh', background: 'var(--color-bg)', fontFamily: 'system-ui,sans-serif' }}>
        <Header />
        <main style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
          <ThemePicker />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
            <DemoCard title="Feature Card" desc="This card uses CSS custom properties — background, border, and text all follow the active theme." />
            <DemoCard title="Another Card" desc="Both primary (filled) and outline button variants adapt to the selected color theme automatically." />
            <DemoCard title="Persistent" desc="Your theme choice is saved in localStorage and restored on next visit. No flicker on load." />
            <DemoCard title="Custom Color" desc="Use the color picker to set any primary color. The CSS var updates instantly across all components." />
          </div>
        </main>
      </div>
    </ThemeProvider>
  )
}
"""),
        tr("Written: src/App.tsx"),
        tc("shell_exec", command="cd workspace/deliverables/theme-picker && npm run build 2>&1 | tail -5"),
        tr("✓ built in 1.0s"),
        tc("undertow"),
        tr("Screenshot: dark app with ocean-blue theme — header with 'Ocean' badge, grid of demo cards with blue primary buttons, theme selector showing 6 preset swatches + custom color input. Cards show primary + outline button variants."),
        tc("message_result", text="**Theme Picker** built.\n\nPattern: `applyTheme()` sets CSS custom properties on `:root` (`--color-primary`, `--color-bg`, etc.) → all components read `var(--color-primary)` → theme change is instant and universal. `useTheme()` wraps context. `localStorage.setItem('app_theme', JSON.stringify(t))` persists across reloads.", done=True),
        tr("Message sent"),
    ]


# ── Main ────────────────────────────────────────────────────────────────────

def build_example(source_fn, messages):
    text = f"<start_of_turn>system\n{SYSTEM_TEXT}<end_of_turn>\n"
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            text += f"<start_of_turn>user\n{content}<end_of_turn>\n"
        elif role in ("assistant", "tool_call", "tool_result"):
            text += f"<start_of_turn>model\n{content}<end_of_turn>\n"
    return {"text": text, "source": source_fn}


def main():
    v92_examples = []
    if V92.exists():
        with open(V92) as f:
            v92_examples = [json.loads(l) for l in f if l.strip()]
        print(f"Loaded {len(v92_examples)} from v92")
    else:
        print("Warning: v92 not found, starting from scratch")

    new_examples = [
        ("dd01_kanban",           dd01_kanban()),
        ("inf01_infinite_scroll", inf01_infinite_scroll()),
        ("md01_markdown_editor",  md01_markdown_editor()),
        ("vc01_theme_picker",     vc01_theme_picker()),
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for ex in v92_examples:
            f.write(json.dumps(ex) + "\n")
        for source, msgs in new_examples:
            obj = build_example(source, msgs)
            f.write(json.dumps(obj) + "\n")
            print(f"  {source}: {len(msgs)} msgs -> {len(obj['text'])} chars")

    total = len(v92_examples) + len(new_examples)
    print(f"\nTotal: {total} ({len(v92_examples)} v92 + {len(new_examples)} new)")
    print(f"Wrote to {OUT}")


if __name__ == "__main__":
    main()
