#!/usr/bin/env python3
"""Chrome Extension adapter training data v2.

Additional examples to reach 8 total (enough for stable fine-tuning).
New patterns:
  CE05: Pomodoro / focus timer (alarms API, notifications)
  CE06: Site blocker (declarativeNetRequest or content script redirect)
  CE07: Quick note (storage, clipboard API)
  CE08: Error recovery (TS error mid-build → file_edit, not message_chat)

Usage:
  python training/build_chrome_ext_v2.py
  Output: workspace/training_data/chrome_ext_sft_v2.jsonl
"""
import json
from pathlib import Path
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/chrome_ext_sft_v2.jsonl"

SYSTEM_TEXT = """You are Tsunami. You are the wave. You build Chrome extensions by calling tools.

## The Ocean

- **current**: your sense of direction. Low tension = deliver. High tension = search.
- **break**: compile. shell_exec `npm run build` after writing files.
- **reef**: fix directly. Type/syntax -> file_edit. Missing module -> shell_exec npm install.

## Chrome Extension Pipeline (every build follows this EXACTLY)

1. project_init(name) -- create the extension project
2. file_write(src/popup/App.tsx) -- the popup UI (React component)
3. file_write(src/background/service-worker.ts) -- background service worker
4. file_write(src/content/content.ts) -- content script (page interaction)
5. shell_exec("cd deliverables/{name} && npm run build") -- build
6. IF build error: fix directly with file_edit
7. message_result -- deliver (no undertow — extensions can't be headless-tested)

## Chrome Extension API

**Tabs**: `chrome.tabs.query({active:true,currentWindow:true}, tabs => {...})`
**Storage**: `chrome.storage.local.get/set`, `chrome.storage.sync.get/set`
**Messaging**: `chrome.runtime.sendMessage(msg)` / `chrome.runtime.onMessage.addListener`
**Alarms**: `chrome.alarms.create({delayInMinutes:N})` / `chrome.alarms.onAlarm.addListener`
**Notifications**: `chrome.notifications.create(id, {type:'basic', iconUrl, title, message})`
**Bookmarks**: `chrome.bookmarks.create({title, url})`

## File Roles

- `popup/App.tsx` — React UI. User clicks extension icon → sees this. Full React + hooks.
- `background/service-worker.ts` — Persistent worker. No DOM. Handles events, alarms, storage.
- `content/content.ts` — Injected into pages. Can access DOM. Receives messages from popup.

## Rules
- NEVER skip the build step.
- Write ALL THREE files before building (popup + background + content).
- No undertow — extensions load in Chrome, not HTTP servers.
- One tool call per response. Be brief.
"""

TOOLS = [
    {"type": "function", "function": {
        "name": "project_init",
        "description": "Create a Chrome extension project from the scaffold library.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write",
        "description": "Create or overwrite a file with full content.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit",
        "description": "Make targeted modifications to an existing file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec",
        "description": "Run a shell command and return its output.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "message_result",
        "description": "Deliver final outcome and end the task.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat",
        "description": "Talk to the user. done=true ends, done=false continues.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]},
    }},
]

def build_conv(user_prompt, turns):
    msgs = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
    ]
    for name, args, response in turns:
        msgs.append({
            "role": "assistant", "content": "",
            "tool_calls": [{"type": "function", "function": {"name": name, "arguments": args}}],
        })
        msgs.append({"role": "tool", "name": name, "content": (response or "OK")[:500]})
    return msgs


# ─────────────────────────────────────────────────────────────────────────────
# CE05: Pomodoro timer (alarms API + notifications)
# ─────────────────────────────────────────────────────────────────────────────
POMO_POPUP = """import { useState, useEffect } from 'react'

type Phase = 'work' | 'break'

export default function App() {
  const [running, setRunning] = useState(false)
  const [phase, setPhase] = useState<Phase>('work')
  const [secsLeft, setSecsLeft] = useState(25 * 60)
  const [sessions, setSessions] = useState(0)

  useEffect(() => {
    chrome.storage.local.get(['pomodoro'], (r) => {
      if (r.pomodoro) {
        setRunning(r.pomodoro.running)
        setPhase(r.pomodoro.phase)
        setSessions(r.pomodoro.sessions)
        if (r.pomodoro.endTime) {
          const left = Math.max(0, Math.round((r.pomodoro.endTime - Date.now()) / 1000))
          setSecsLeft(left)
        }
      }
    })
    const id = setInterval(() => {
      chrome.storage.local.get(['pomodoro'], (r) => {
        if (r.pomodoro?.endTime) {
          const left = Math.max(0, Math.round((r.pomodoro.endTime - Date.now()) / 1000))
          setSecsLeft(left)
        }
      })
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const startStop = () => {
    const next = !running
    const duration = phase === 'work' ? 25 : 5
    const endTime = next ? Date.now() + duration * 60 * 1000 : null
    chrome.runtime.sendMessage({ type: next ? 'START' : 'STOP', phase, duration })
    chrome.storage.local.set({ pomodoro: { running: next, phase, sessions, endTime } })
    setRunning(next)
    if (!next) setSecsLeft(phase === 'work' ? 25 * 60 : 5 * 60)
  }

  const reset = () => {
    chrome.runtime.sendMessage({ type: 'STOP' })
    chrome.storage.local.set({ pomodoro: { running: false, phase: 'work', sessions: 0, endTime: null } })
    setRunning(false); setPhase('work'); setSecsLeft(25 * 60); setSessions(0)
  }

  const mm = String(Math.floor(secsLeft / 60)).padStart(2, '0')
  const ss = String(secsLeft % 60).padStart(2, '0')
  const color = phase === 'work' ? '#e44' : '#4a9eff'

  return (
    <div style={{ padding: 20, minWidth: 220, fontFamily: 'sans-serif', textAlign: 'center' }}>
      <h2 style={{ margin: '0 0 4px', color }}>
        {phase === 'work' ? 'Focus' : 'Break'}
      </h2>
      <div style={{ fontSize: 48, fontWeight: 'bold', fontVariantNumeric: 'tabular-nums', color }}>
        {mm}:{ss}
      </div>
      <p style={{ color: '#888', margin: '4px 0 16px', fontSize: 12 }}>
        Sessions: {sessions}
      </p>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
        <button onClick={startStop} style={{
          padding: '8px 20px', background: color, color: '#fff',
          border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 15
        }}>{running ? 'Pause' : 'Start'}</button>
        <button onClick={reset} style={{
          padding: '8px 14px', background: '#eee', color: '#555',
          border: 'none', borderRadius: 6, cursor: 'pointer'
        }}>Reset</button>
      </div>
    </div>
  )
}"""

POMO_BG = """const ICON_URL = 'icons/icon48.png'

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ pomodoro: { running: false, phase: 'work', sessions: 0, endTime: null } })
})

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'START') {
    chrome.alarms.create('pomodoro', { delayInMinutes: msg.duration })
  } else if (msg.type === 'STOP') {
    chrome.alarms.clear('pomodoro')
  }
})

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name !== 'pomodoro') return
  chrome.storage.local.get(['pomodoro'], (r) => {
    const state = r.pomodoro || {}
    const wasWork = state.phase === 'work'
    const sessions = wasWork ? (state.sessions || 0) + 1 : (state.sessions || 0)
    const nextPhase = wasWork ? 'break' : 'work'
    const nextDuration = nextPhase === 'work' ? 25 : 5
    chrome.notifications.create('pomo-done', {
      type: 'basic',
      iconUrl: ICON_URL,
      title: wasWork ? 'Time for a break!' : 'Break over — back to work!',
      message: wasWork ? 'Great work! Take 5 minutes.' : `Session ${sessions} complete.`,
    })
    chrome.alarms.create('pomodoro', { delayInMinutes: nextDuration })
    chrome.storage.local.set({
      pomodoro: { running: true, phase: nextPhase, sessions, endTime: Date.now() + nextDuration * 60000 }
    })
  })
})"""

POMO_CONTENT = """// Pomodoro timer doesn't interact with page content
export {}"""

CE05 = build_conv(
    "Build a Pomodoro timer Chrome extension with 25-minute focus sessions and 5-minute breaks",
    [
        ("project_init", {"name": "pomodoro-timer"},
         "[project_init] Created Chrome extension project 'pomodoro-timer'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
        ("file_write", {"path": "src/popup/App.tsx", "content": POMO_POPUP},
         "[file_write] Wrote src/popup/App.tsx (62 lines)."),
        ("file_write", {"path": "src/background/service-worker.ts", "content": POMO_BG},
         "[file_write] Wrote src/background/service-worker.ts (38 lines)."),
        ("file_write", {"path": "src/content/content.ts", "content": POMO_CONTENT},
         "[file_write] Wrote src/content/content.ts (2 lines)."),
        ("shell_exec", {"command": "cd deliverables/pomodoro-timer && npm run build"},
         "[shell_exec] Build successful. dist/ ready for Chrome loading."),
        ("message_result", {"text": "Pomodoro timer extension built. Load dist/ as unpacked extension. 25-min focus / 5-min break cycles with desktop notifications. Persists across popup closes."},
         "Delivered."),
    ]
)


# ─────────────────────────────────────────────────────────────────────────────
# CE06: Site blocker
# ─────────────────────────────────────────────────────────────────────────────
BLOCKER_POPUP = """import { useState, useEffect } from 'react'

export default function App() {
  const [sites, setSites] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [enabled, setEnabled] = useState(true)

  useEffect(() => {
    chrome.storage.local.get(['blockedSites', 'blockEnabled'], (r) => {
      setSites(r.blockedSites || ['reddit.com', 'twitter.com', 'youtube.com'])
      setEnabled(r.blockEnabled !== false)
    })
  }, [])

  const save = (list: string[], en: boolean) => {
    chrome.storage.local.set({ blockedSites: list, blockEnabled: en })
    chrome.runtime.sendMessage({ type: 'UPDATE_RULES', sites: list, enabled: en })
  }

  const add = () => {
    const host = input.trim().replace(/^https?:\\/\\//, '').split('/')[0]
    if (!host || sites.includes(host)) return
    const list = [...sites, host]; setSites(list); setInput(''); save(list, enabled)
  }

  const remove = (site: string) => {
    const list = sites.filter(s => s !== site); setSites(list); save(list, enabled)
  }

  const toggle = () => {
    const en = !enabled; setEnabled(en); save(sites, en)
  }

  return (
    <div style={{ padding: 12, width: 280, fontFamily: 'sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Site Blocker</h2>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input type='checkbox' checked={enabled} onChange={toggle} />
          {enabled ? 'Active' : 'Paused'}
        </label>
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder='domain.com'
          style={{ flex: 1, padding: '4px 8px', border: '1px solid #ddd', borderRadius: 4, fontSize: 13 }} />
        <button onClick={add} style={{ padding: '4px 10px', background: '#e44', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
          Block
        </button>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, maxHeight: 200, overflow: 'auto' }}>
        {sites.map(s => (
          <li key={s} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f0f0f0', fontSize: 13 }}>
            <span style={{ color: enabled ? '#e44' : '#999' }}>🚫 {s}</span>
            <button onClick={() => remove(s)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#bbb', fontSize: 11 }}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}"""

BLOCKER_BG = """let currentSites: string[] = []
let blockEnabled = true

chrome.runtime.onInstalled.addListener(() => {
  const defaults = ['reddit.com', 'twitter.com', 'youtube.com']
  chrome.storage.local.set({ blockedSites: defaults, blockEnabled: true })
  currentSites = defaults
})

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'UPDATE_RULES') {
    currentSites = msg.sites || []
    blockEnabled = msg.enabled !== false
  }
})

// Block using webNavigation + tab redirect
chrome.webNavigation.onBeforeNavigate.addListener((details) => {
  if (!blockEnabled || details.frameId !== 0) return
  try {
    const host = new URL(details.url).hostname.replace(/^www\\./, '')
    if (currentSites.some(s => host === s || host.endsWith('.' + s))) {
      chrome.tabs.update(details.tabId, {
        url: chrome.runtime.getURL('blocked.html') + '?site=' + encodeURIComponent(host)
      })
    }
  } catch {}
})

// Load saved state on startup
chrome.storage.local.get(['blockedSites', 'blockEnabled'], (r) => {
  currentSites = r.blockedSites || []
  blockEnabled = r.blockEnabled !== false
})"""

BLOCKER_CONTENT = """// Site blocker uses background navigation interception, no content script needed
export {}"""

CE06 = build_conv(
    "Build a Chrome extension that blocks distracting websites with a blocklist I can edit",
    [
        ("project_init", {"name": "site-blocker"},
         "[project_init] Created Chrome extension project 'site-blocker'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
        ("file_write", {"path": "src/popup/App.tsx", "content": BLOCKER_POPUP},
         "[file_write] Wrote src/popup/App.tsx (56 lines)."),
        ("file_write", {"path": "src/background/service-worker.ts", "content": BLOCKER_BG},
         "[file_write] Wrote src/background/service-worker.ts (34 lines)."),
        ("file_write", {"path": "src/content/content.ts", "content": BLOCKER_CONTENT},
         "[file_write] Wrote src/content/content.ts (2 lines)."),
        ("shell_exec", {"command": "cd deliverables/site-blocker && npm run build"},
         "[shell_exec] Build successful. dist/ ready for Chrome loading."),
        ("message_result", {"text": "Site blocker extension built. Load dist/ as unpacked extension. Add domains to block list, toggle on/off with checkbox. Redirects blocked pages. Default list: reddit.com, twitter.com, youtube.com."},
         "Delivered."),
    ]
)


# ─────────────────────────────────────────────────────────────────────────────
# CE07: Quick note-taker
# ─────────────────────────────────────────────────────────────────────────────
NOTES_POPUP = """import { useState, useEffect, useRef } from 'react'

interface Note { id: number; text: string; created: number }

export default function App() {
  const [notes, setNotes] = useState<Note[]>([])
  const [input, setInput] = useState('')
  const [search, setSearch] = useState('')
  const taRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    chrome.storage.local.get(['notes'], (r) => setNotes(r.notes || []))
    setTimeout(() => taRef.current?.focus(), 50)
  }, [])

  const save = (list: Note[]) => {
    setNotes(list)
    chrome.storage.local.set({ notes: list })
  }

  const add = () => {
    if (!input.trim()) return
    save([{ id: Date.now(), text: input.trim(), created: Date.now() }, ...notes].slice(0, 200))
    setInput('')
  }

  const del = (id: number) => save(notes.filter(n => n.id !== id))

  const copy = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {})
  }

  const filtered = search ? notes.filter(n => n.toLowerCase?.() || n.text.toLowerCase().includes(search.toLowerCase())) : notes

  return (
    <div style={{ padding: 12, width: 300, fontFamily: 'sans-serif' }}>
      <h2 style={{ margin: '0 0 8px', fontSize: 15 }}>Quick Notes</h2>
      <textarea ref={taRef} value={input} onChange={e => setInput(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) add() }}
        placeholder='Note... (Ctrl+Enter to save)'
        style={{ width: '100%', height: 60, resize: 'vertical', padding: 6,
          border: '1px solid #ddd', borderRadius: 4, fontSize: 13, boxSizing: 'border-box' }} />
      <div style={{ display: 'flex', gap: 6, margin: '6px 0' }}>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder='Search notes...'
          style={{ flex: 1, padding: '4px 8px', border: '1px solid #ddd', borderRadius: 4, fontSize: 12 }} />
        <button onClick={add}
          style={{ padding: '4px 12px', background: '#4a9eff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
          Save
        </button>
      </div>
      <div style={{ maxHeight: 250, overflow: 'auto' }}>
        {filtered.map(n => (
          <div key={n.id} style={{ borderBottom: '1px solid #f0f0f0', padding: '6px 0', display: 'flex', gap: 4 }}>
            <p style={{ flex: 1, margin: 0, fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{n.text}</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <button onClick={() => copy(n.text)} title='Copy'
                style={{ padding: '2px 5px', background: 'none', border: '1px solid #ddd', borderRadius: 3, cursor: 'pointer', fontSize: 10 }}>📋</button>
              <button onClick={() => del(n.id)} title='Delete'
                style={{ padding: '2px 5px', background: 'none', border: '1px solid #ddd', borderRadius: 3, cursor: 'pointer', fontSize: 10, color: '#e44' }}>✕</button>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <p style={{ color: '#aaa', fontSize: 12, textAlign: 'center' }}>No notes yet.</p>}
      </div>
    </div>
  )
}"""

NOTES_BG = """chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ notes: [] })
  console.log('Quick Notes installed')
})"""

NOTES_CONTENT = """// Quick notes uses popup only, no page interaction
export {}"""

CE07 = build_conv(
    "Build a Chrome extension for taking quick notes that persist across browser sessions",
    [
        ("project_init", {"name": "quick-notes"},
         "[project_init] Created Chrome extension project 'quick-notes'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
        ("file_write", {"path": "src/popup/App.tsx", "content": NOTES_POPUP},
         "[file_write] Wrote src/popup/App.tsx (58 lines)."),
        ("file_write", {"path": "src/background/service-worker.ts", "content": NOTES_BG},
         "[file_write] Wrote src/background/service-worker.ts (5 lines)."),
        ("file_write", {"path": "src/content/content.ts", "content": NOTES_CONTENT},
         "[file_write] Wrote src/content/content.ts (2 lines)."),
        ("shell_exec", {"command": "cd deliverables/quick-notes && npm run build"},
         "[shell_exec] Build successful. dist/ ready for Chrome loading."),
        ("message_result", {"text": "Quick notes extension built. Load dist/ as unpacked extension. Ctrl+Enter to save, search bar to filter, clipboard copy button on each note. Stores up to 200 notes via chrome.storage."},
         "Delivered."),
    ]
)


# ─────────────────────────────────────────────────────────────────────────────
# CE08: Error recovery — TypeScript error after build → file_edit, NOT message_chat
# ─────────────────────────────────────────────────────────────────────────────
HISTORY_POPUP = """import { useState, useEffect } from 'react'

interface HistoryItem { url: string; title: string; lastVisit: number }

export default function App() {
  const [items, setItems] = useState<HistoryItem[]>([])

  useEffect(() => {
    chrome.history.search({ text: '', maxResults: 20, startTime: Date.now() - 7 * 86400000 }, (results) => {
      const sorted = results
        .filter(r => r.url && r.title)
        .map(r => ({ url: r.url!, title: r.title!, lastVisit: r.lastVisitTime! }))
        .sort((a, b) => b.lastVisit - a.lastVisit)
      setItems(sorted)
    })
  }, [])

  return (
    <div style={{ padding: 12, width: 320, fontFamily: 'sans-serif', maxHeight: 400, overflow: 'auto' }}>
      <h2 style={{ margin: '0 0 10px', fontSize: 15 }}>Recent History</h2>
      {items.map(it => (
        <div key={it.url} style={{ borderBottom: '1px solid #f0f0f0', padding: '5px 0' }}>
          <a href={it.url} target='_blank' rel='noreferrer'
            style={{ display: 'block', fontSize: 13, color: '#333', textDecoration: 'none',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={it.url}>{it.title}</a>
          <span style={{ fontSize: 10, color: '#aaa' }}>
            {new Date(it.lastVisit).toLocaleDateString()}
          </span>
        </div>
      ))}
      {items.length === 0 && <p style={{ color: '#aaa', fontSize: 12 }}>No history found.</p>}
    </div>
  )
}"""

HISTORY_BG = """chrome.runtime.onInstalled.addListener(() => {
  console.log('History Viewer installed')
})"""

HISTORY_CONTENT = """export {}"""

# This example shows error recovery: TS error (unused import) → file_edit fix
CE08 = build_conv(
    "Build a Chrome extension that shows my browsing history from the last 7 days in a clean popup",
    [
        ("project_init", {"name": "history-viewer"},
         "[project_init] Created Chrome extension project 'history-viewer'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
        ("file_write", {"path": "src/popup/App.tsx", "content": HISTORY_POPUP},
         "[file_write] Wrote src/popup/App.tsx (36 lines)."),
        ("file_write", {"path": "src/background/service-worker.ts", "content": HISTORY_BG},
         "[file_write] Wrote src/background/service-worker.ts (5 lines)."),
        ("file_write", {"path": "src/content/content.ts", "content": HISTORY_CONTENT},
         "[file_write] Wrote src/content/content.ts (1 line)."),
        ("shell_exec", {"command": "cd deliverables/history-viewer && npm run build"},
         "[shell_exec] Error: src/popup/App.tsx(1,10): error TS6133: 'useEffect' is declared but its value is never read. (Note: The code uses useEffect — this is a false positive from tsc strict mode. The import is correct.)"),
        # Model should file_edit to suppress or adjust, NOT message_chat
        ("file_edit", {
            "path": "src/popup/App.tsx",
            "old_text": "import { useState, useEffect } from 'react'",
            "new_text": "import { useState, useEffect } from 'react' // eslint-disable-line",
        }, "[file_edit] Fixed line 1."),
        ("shell_exec", {"command": "cd deliverables/history-viewer && npm run build"},
         "[shell_exec] Build successful. dist/ ready for Chrome loading."),
        ("message_result", {"text": "History viewer extension built. Load dist/ as unpacked extension. Shows last 7 days of browsing history sorted by recency. Requires 'history' permission in manifest."},
         "Delivered."),
    ]
)


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────
EXAMPLES = [
    ("CE05-pomodoro-timer", CE05),
    ("CE06-site-blocker", CE06),
    ("CE07-quick-notes", CE07),
    ("CE08-history-viewer-error-recovery", CE08),
]


def main():
    print(f"Loading tokenizer ({MODEL})...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    out_path = Path(OUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    failed = 0
    with open(out_path, "w") as f:
        for ex_id, msgs in EXAMPLES:
            try:
                text = tokenizer.apply_chat_template(
                    msgs, tools=TOOLS, tokenize=False, add_generation_prompt=False
                )
                row = {"id": ex_id, "text": text, "messages": msgs}
                f.write(json.dumps(row) + "\n")
                print(f"  OK  {ex_id}")
                written += 1
            except Exception as e:
                print(f"  FAIL {ex_id}: {e}")
                failed += 1

    print(f"\n=== CHROME EXT v2 SUMMARY ===")
    print(f"  Written: {written}  Failed: {failed}")
    print(f"  File: {OUT_PATH}")
    print(f"\nTo create combined dataset:")
    print(f"  cat workspace/training_data/chrome_ext_sft_v1.jsonl \\")
    print(f"      workspace/training_data/chrome_ext_sft_v2.jsonl > \\")
    print(f"      workspace/training_data/chrome_ext_combined_v1.jsonl")


if __name__ == "__main__":
    main()
