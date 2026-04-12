#!/usr/bin/env python3
"""Chrome Extension adapter training data v1.

Distinct from the build adapter: chrome extensions have a 3-file structure
(popup, background service-worker, content script), use the chrome.* API,
can't be undertow-tested (no HTTP server), and have different delivery semantics.

New adapter: chrome-ext-v1
Route trigger: "chrome extension", "browser extension", "popup extension"

Examples:
  CE01: Tab counter (tabs API, storage)
  CE02: Page word counter (content script, DOM)
  CE03: Quick bookmark (tabs + bookmarks API)
  CE04: Dark mode toggle (content script, CSS injection)

Usage:
  python training/build_chrome_ext_v1.py
  Output: workspace/training_data/chrome_ext_sft_v1.jsonl
"""
import json
from pathlib import Path
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/chrome_ext_sft_v1.jsonl"

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
**Alarms**: `chrome.alarms.create/onAlarm.addListener`
**Bookmarks**: `chrome.bookmarks.create({title, url})` 
**Scripting**: `chrome.scripting.executeScript({target:{tabId}, func})`
**Notifications**: `chrome.notifications.create({type:'basic', title, message})`

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
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Search the web for information.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
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


# ──────────────────────────────────────────────────────────────────────────────
# CE01: Tab counter extension
# ──────────────────────────────────────────────────────────────────────────────
TABCOUNT_POPUP = """import { useState, useEffect } from 'react'

export default function App() {
  const [tabCount, setTabCount] = useState(0)
  const [windowCount, setWindowCount] = useState(0)

  useEffect(() => {
    chrome.tabs.query({}, (tabs) => setTabCount(tabs.length))
    chrome.windows.getAll({}, (windows) => setWindowCount(windows.length))
    // update every 2 seconds
    const id = setInterval(() => {
      chrome.tabs.query({}, (tabs) => setTabCount(tabs.length))
    }, 2000)
    return () => clearInterval(id)
  }, [])

  const closeAll = () => {
    chrome.tabs.query({ active: false, currentWindow: true }, (tabs) => {
      tabs.forEach(t => chrome.tabs.remove(t.id!))
    })
  }

  return (
    <div style={{ padding: 16, minWidth: 200, fontFamily: 'sans-serif' }}>
      <h2 style={{ margin: '0 0 12px' }}>Tab Counter</h2>
      <p><strong>{tabCount}</strong> open tabs</p>
      <p><strong>{windowCount}</strong> windows</p>
      <button onClick={closeAll}
        style={{ padding: '6px 12px', background: '#e44', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
        Close background tabs
      </button>
    </div>
  )
}"""

TABCOUNT_BG = """chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ installed: Date.now() })
  console.log('Tab Counter installed')
})

// Badge shows tab count
function updateBadge() {
  chrome.tabs.query({}, (tabs) => {
    chrome.action.setBadgeText({ text: String(tabs.length) })
    chrome.action.setBadgeBackgroundColor({ color: '#4a9eff' })
  })
}

chrome.tabs.onCreated.addListener(updateBadge)
chrome.tabs.onRemoved.addListener(updateBadge)
updateBadge()"""

TABCOUNT_CONTENT = """// Tab counter doesn't need content script — passive extension
export {}"""

CE01 = build_conv(
    "Build a Chrome extension that shows how many tabs I have open with a badge count",
    [
        ("project_init", {"name": "tab-counter"},
         "[project_init] Created Chrome extension project 'tab-counter'. Write popup/App.tsx, background/service-worker.ts, and content/content.ts."),
        ("file_write", {"path": "src/popup/App.tsx", "content": TABCOUNT_POPUP},
         "[file_write] Wrote src/popup/App.tsx (38 lines)."),
        ("file_write", {"path": "src/background/service-worker.ts", "content": TABCOUNT_BG},
         "[file_write] Wrote src/background/service-worker.ts (16 lines)."),
        ("file_write", {"path": "src/content/content.ts", "content": TABCOUNT_CONTENT},
         "[file_write] Wrote src/content/content.ts (2 lines)."),
        ("shell_exec", {"command": "cd deliverables/tab-counter && npm run build"},
         "[shell_exec] Build successful. dist/ ready for Chrome loading."),
        ("message_result", {"text": "Tab counter extension built. Load dist/ as unpacked extension in Chrome. Badge shows live tab count. 'Close background tabs' button removes inactive tabs."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# CE02: Page word counter
# ──────────────────────────────────────────────────────────────────────────────
WORDCOUNT_POPUP = """import { useState, useEffect } from 'react'

interface WordStats { words: number; chars: number; readTime: string }

export default function App() {
  const [stats, setStats] = useState<WordStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'COUNT_WORDS' }, (response) => {
          if (response) { setStats(response); setLoading(false) }
        })
      }
    })
  }, [])

  return (
    <div style={{ padding: 16, minWidth: 200, fontFamily: 'sans-serif' }}>
      <h2 style={{ margin: '0 0 12px' }}>Page Word Count</h2>
      {loading ? <p>Counting...</p> : stats ? (
        <>
          <p><strong>{stats.words.toLocaleString()}</strong> words</p>
          <p><strong>{stats.chars.toLocaleString()}</strong> characters</p>
          <p>~{stats.readTime} read</p>
        </>
      ) : <p style={{ color: '#e44' }}>Could not count — try reloading page.</p>}
    </div>
  )
}"""

WORDCOUNT_BG = """chrome.runtime.onInstalled.addListener(() => {
  console.log('Word Counter installed')
})"""

WORDCOUNT_CONTENT = """chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'COUNT_WORDS') {
    // Extract visible text from the page body
    const text = document.body.innerText || ''
    const words = text.trim().split(/\\s+/).filter(w => w.length > 0).length
    const chars = text.replace(/\\s/g, '').length
    const minutes = Math.ceil(words / 200) // avg 200 wpm
    const readTime = minutes < 60
      ? `${minutes} min`
      : `${Math.floor(minutes/60)}h ${minutes%60}m`
    sendResponse({ words, chars, readTime })
  }
  return true
})"""

CE02 = build_conv(
    "Build a Chrome extension popup that shows word count and estimated reading time for the current page",
    [
        ("project_init", {"name": "word-counter"},
         "[project_init] Created Chrome extension project 'word-counter'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
        ("file_write", {"path": "src/popup/App.tsx", "content": WORDCOUNT_POPUP},
         "[file_write] Wrote src/popup/App.tsx (36 lines)."),
        ("file_write", {"path": "src/background/service-worker.ts", "content": WORDCOUNT_BG},
         "[file_write] Wrote src/background/service-worker.ts (4 lines)."),
        ("file_write", {"path": "src/content/content.ts", "content": WORDCOUNT_CONTENT},
         "[file_write] Wrote src/content/content.ts (18 lines)."),
        ("shell_exec", {"command": "cd deliverables/word-counter && npm run build"},
         "[shell_exec] Build successful. dist/ ready for Chrome loading."),
        ("message_result", {"text": "Word counter extension built. Load dist/ as unpacked extension. Click the icon while on any page to see word count and reading time estimate."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# CE03: Quick bookmark / save-for-later
# ──────────────────────────────────────────────────────────────────────────────
BOOKMARK_POPUP = """import { useState, useEffect } from 'react'

interface Bookmark { url: string; title: string; savedAt: number }

export default function App() {
  const [saved, setSaved] = useState<Bookmark[]>([])
  const [status, setStatus] = useState('')

  useEffect(() => {
    chrome.storage.local.get(['bookmarks'], (r) => setSaved(r.bookmarks || []))
  }, [])

  const saveCurrentPage = () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0]
      if (!tab?.url || !tab?.title) return
      const b: Bookmark = { url: tab.url, title: tab.title, savedAt: Date.now() }
      chrome.storage.local.get(['bookmarks'], (r) => {
        const list = [b, ...(r.bookmarks || [])].slice(0, 50)
        chrome.storage.local.set({ bookmarks: list })
        setSaved(list)
        setStatus('Saved!')
        setTimeout(() => setStatus(''), 1500)
      })
    })
  }

  const remove = (url: string) => {
    const list = saved.filter(b => b.url !== url)
    chrome.storage.local.set({ bookmarks: list })
    setSaved(list)
  }

  return (
    <div style={{ padding: 12, width: 320, fontFamily: 'sans-serif', maxHeight: 400, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Quick Bookmarks</h2>
        <button onClick={saveCurrentPage}
          style={{ padding: '4px 10px', background: '#4a9eff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
          {status || '+ Save'}
        </button>
      </div>
      {saved.length === 0 ? <p style={{ color: '#888', fontSize: 13 }}>No saves yet. Browse to a page and click + Save.</p> : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {saved.map(b => (
            <li key={b.url} style={{ borderBottom: '1px solid #eee', padding: '6px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
              <a href={b.url} target='_blank' rel='noreferrer'
                style={{ flex: 1, fontSize: 13, color: '#333', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                title={b.url}>{b.title}</a>
              <button onClick={() => remove(b.url)}
                style={{ padding: '2px 6px', background: 'none', border: '1px solid #ddd', borderRadius: 3, cursor: 'pointer', fontSize: 11, color: '#888' }}>✕</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}"""

BOOKMARK_BG = """chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ bookmarks: [] })
  console.log('Quick Bookmarks installed')
})"""

BOOKMARK_CONTENT = """// No DOM interaction needed for this extension
export {}"""

CE03 = build_conv(
    "Build a Chrome extension for saving pages to read later — like a mini pocket/bookmarks list",
    [
        ("project_init", {"name": "quick-bookmarks"},
         "[project_init] Created Chrome extension project 'quick-bookmarks'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
        ("file_write", {"path": "src/popup/App.tsx", "content": BOOKMARK_POPUP},
         "[file_write] Wrote src/popup/App.tsx (52 lines)."),
        ("file_write", {"path": "src/background/service-worker.ts", "content": BOOKMARK_BG},
         "[file_write] Wrote src/background/service-worker.ts (5 lines)."),
        ("file_write", {"path": "src/content/content.ts", "content": BOOKMARK_CONTENT},
         "[file_write] Wrote src/content/content.ts (2 lines)."),
        ("shell_exec", {"command": "cd deliverables/quick-bookmarks && npm run build"},
         "[shell_exec] Build successful. dist/ ready for Chrome loading."),
        ("message_result", {"text": "Quick bookmarks extension built. Load dist/ as unpacked extension. Click the icon to save any page — persists up to 50 entries via chrome.storage."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# CE04: Dark mode toggle
# ──────────────────────────────────────────────────────────────────────────────
DARKMODE_POPUP = """import { useState, useEffect } from 'react'

export default function App() {
  const [enabled, setEnabled] = useState(false)
  const [url, setUrl] = useState('')

  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0]
      if (tab?.url) setUrl(new URL(tab.url).hostname)
      if (tab?.id) {
        chrome.tabs.sendMessage(tab.id, { type: 'GET_DARK_STATE' }, (r) => {
          if (r) setEnabled(r.enabled)
        })
      }
    })
  }, [])

  const toggle = () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'TOGGLE_DARK' }, (r) => {
          if (r) setEnabled(r.enabled)
        })
      }
    })
  }

  return (
    <div style={{ padding: 16, minWidth: 200, fontFamily: 'sans-serif' }}>
      <h2 style={{ margin: '0 0 8px' }}>Dark Mode</h2>
      {url && <p style={{ margin: '0 0 12px', color: '#666', fontSize: 12 }}>{url}</p>}
      <button onClick={toggle} style={{
        padding: '8px 20px',
        background: enabled ? '#333' : '#f5f5f5',
        color: enabled ? '#fff' : '#333',
        border: '2px solid #ddd',
        borderRadius: 6,
        cursor: 'pointer',
        fontSize: 14,
        width: '100%',
      }}>
        {enabled ? '☀️ Turn Off' : '🌙 Turn On'}
      </button>
    </div>
  )
}"""

DARKMODE_BG = """chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ darkSites: {} })
  console.log('Dark Mode Toggle installed')
})"""

DARKMODE_CONTENT = """let darkEnabled = false

// Inject CSS filter for dark mode
const DARK_STYLE_ID = '__tsunami_dark_mode__'

function applyDark() {
  let el = document.getElementById(DARK_STYLE_ID) as HTMLStyleElement | null
  if (!el) {
    el = document.createElement('style')
    el.id = DARK_STYLE_ID
    document.head.appendChild(el)
  }
  el.textContent = [
    'html { filter: invert(1) hue-rotate(180deg); }',
    'img, video, canvas, svg { filter: invert(1) hue-rotate(180deg); }',
  ].join('\\n')
}

function removeDark() {
  const el = document.getElementById(DARK_STYLE_ID)
  if (el) el.remove()
}

// Restore persisted state on load
chrome.storage.local.get(['darkSites'], (r) => {
  const sites = r.darkSites || {}
  if (sites[location.hostname]) { darkEnabled = true; applyDark() }
})

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'GET_DARK_STATE') {
    sendResponse({ enabled: darkEnabled })
  } else if (msg.type === 'TOGGLE_DARK') {
    darkEnabled = !darkEnabled
    darkEnabled ? applyDark() : removeDark()
    chrome.storage.local.get(['darkSites'], (r) => {
      const sites = r.darkSites || {}
      if (darkEnabled) sites[location.hostname] = true
      else delete sites[location.hostname]
      chrome.storage.local.set({ darkSites: sites })
    })
    sendResponse({ enabled: darkEnabled })
  }
  return true
})"""

CE04 = build_conv(
    "Build a Chrome extension that toggles dark mode on any website using CSS filter inversion",
    [
        ("project_init", {"name": "dark-mode-toggle"},
         "[project_init] Created Chrome extension project 'dark-mode-toggle'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
        ("file_write", {"path": "src/popup/App.tsx", "content": DARKMODE_POPUP},
         "[file_write] Wrote src/popup/App.tsx (40 lines)."),
        ("file_write", {"path": "src/background/service-worker.ts", "content": DARKMODE_BG},
         "[file_write] Wrote src/background/service-worker.ts (6 lines)."),
        ("file_write", {"path": "src/content/content.ts", "content": DARKMODE_CONTENT},
         "[file_write] Wrote src/content/content.ts (44 lines)."),
        ("shell_exec", {"command": "cd deliverables/dark-mode-toggle && npm run build"},
         "[shell_exec] Build successful. dist/ ready for Chrome loading."),
        ("message_result", {"text": "Dark mode toggle built. Load dist/ as unpacked extension. Click icon on any page to toggle dark mode (CSS filter invert). Remembers per-domain preference."},
         "Delivered."),
    ]
)

# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────
EXAMPLES = [
    ("CE01-tab-counter", CE01),
    ("CE02-word-counter", CE02),
    ("CE03-quick-bookmarks", CE03),
    ("CE04-dark-mode-toggle", CE04),
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

    print(f"\n=== CHROME EXT v1 SUMMARY ===")
    print(f"  Written: {written}  Failed: {failed}")
    print(f"  File: {OUT_PATH}")
    print(f"\nTo train:")
    print(f"  python training/train_unsloth.py \\")
    print(f"    --model google/gemma-4-e4b-it \\")
    print(f"    --data workspace/training_data/chrome_ext_sft_v1.jsonl \\")
    print(f"    --output models/gemma-4-e4b-tsunami-chrome-ext-v1 \\")
    print(f"    --epochs 3 --lora-r 16 --lr 2e-4")


if __name__ == "__main__":
    main()
