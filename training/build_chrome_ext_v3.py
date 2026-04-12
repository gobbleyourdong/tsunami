#!/usr/bin/env python3
"""Chrome Extension training data v3 -- new API surfaces.

New patterns (reaching 12 total SFT examples):
  CE09: Keyboard shortcuts (chrome.commands API)
  CE10: Context menu items (chrome.contextMenus + messaging)
  CE11: Download tracker (chrome.downloads.onCreated listener)
  CE12: New tab dashboard (chrome.tabs, fetch API for quotes/news)

Usage:
  python training/build_chrome_ext_v3.py
  Output: workspace/training_data/chrome_ext_sft_v3.jsonl
  Combined: workspace/training_data/chrome_ext_combined_v2.jsonl
"""
import json
from pathlib import Path
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/chrome_ext_sft_v3.jsonl"
COMBINED_PATH = "workspace/training_data/chrome_ext_combined_v2.jsonl"

SYSTEM_TEXT = """You are Tsunami. You are the wave. You build Chrome extensions by calling tools.

## Chrome Extension Pipeline (every build follows this EXACTLY)

1. project_init(name) -- create the extension project
2. file_write(src/popup/App.tsx) -- the popup UI (React component)
3. file_write(src/background/service-worker.ts) -- background service worker
4. file_write(src/content/content.ts) -- content script (page interaction)
5. shell_exec("cd deliverables/{name} && npm run build") -- build
6. IF build error: fix directly with file_edit
7. message_result -- deliver (no undertow -- extensions can't be headless-tested)

## Chrome Extension API

Tabs: chrome.tabs.query({active:true,currentWindow:true}, tabs => {...})
Storage: chrome.storage.local.get/set, chrome.storage.sync.get/set
Messaging: chrome.runtime.sendMessage(msg) / chrome.runtime.onMessage.addListener
Alarms: chrome.alarms.create({delayInMinutes:N}) / chrome.alarms.onAlarm.addListener
Notifications: chrome.notifications.create(id, {type:'basic', iconUrl, title, message})
Commands: chrome.commands.onCommand.addListener(cmd => {...}) -- keyboard shortcuts
ContextMenus: chrome.contextMenus.create({id, title, contexts}) -- right-click menus
Downloads: chrome.downloads.onCreated.addListener(item => {...}) -- download events
Bookmarks: chrome.bookmarks.create({title, url})

## Rules
- NEVER skip the build step.
- Write ALL THREE files before building (popup + background + content).
- No undertow -- extensions load in Chrome, not HTTP servers.
- One tool call per response. Be brief.
"""

TOOLS = [
    {"type": "function", "function": {
        "name": "project_init", "description": "Create a Chrome extension project.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write", "description": "Create or overwrite a file with full content.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit", "description": "Make targeted modifications to an existing file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec", "description": "Run a shell command.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "message_result", "description": "Deliver final outcome.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat", "description": "Talk to the user.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]},
    }},
]

print("Loading tokenizer (google/gemma-4-e4b-it)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
print("Tokenizer loaded.")


def build_conv(user_prompt, turns):
    msgs = [
        {"role": "system", "content": SYSTEM_TEXT},
        {"role": "user", "content": user_prompt},
    ]
    for name, args, response in turns:
        msgs.append({
            "role": "assistant", "content": "",
            "tool_calls": [{"type": "function", "function": {"name": name, "arguments": json.dumps(args) if isinstance(args, dict) else args}}],
        })
        msgs.append({"role": "tool", "name": name, "content": (response or "OK")[:500]})
    return msgs


def tokenize(msgs):
    return {"text": tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)}


examples = []

# ─────────────────────────────────────────────────────────────────────────────
# CE09: Keyboard shortcut launcher (chrome.commands API)
# ─────────────────────────────────────────────────────────────────────────────

CE09_POPUP = (
    "import { useState, useEffect } from 'react'\n\n"
    "export default function App() {\n"
    "  const [shortcuts, setShortcuts] = useState<chrome.commands.Command[]>([])\n\n"
    "  useEffect(() => {\n"
    "    chrome.commands.getAll(cmds => setShortcuts(cmds))\n"
    "  }, [])\n\n"
    "  return (\n"
    "    <div style={{padding:'12px',minWidth:'240px'}}>\n"
    "      <h3 style={{margin:'0 0 8px'}}>Keyboard Shortcuts</h3>\n"
    "      {shortcuts.map(s => (\n"
    "        <div key={s.name} style={{display:'flex',justifyContent:'space-between',padding:'4px 0',fontSize:'13px'}}>\n"
    "          <span>{s.description || s.name}</span>\n"
    "          <kbd style={{background:'#f0f0f0',padding:'2px 6px',borderRadius:'3px'}}>\n"
    "            {s.shortcut || '(not set)'}\n"
    "          </kbd>\n"
    "        </div>\n"
    "      ))}\n"
    "    </div>\n"
    "  )\n"
    "}\n"
)

CE09_BG = (
    "chrome.commands.onCommand.addListener((command) => {\n"
    "  if (command === 'open-search') {\n"
    "    chrome.tabs.create({ url: 'https://www.google.com' })\n"
    "  } else if (command === 'close-tab') {\n"
    "    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {\n"
    "      if (tabs[0]?.id) chrome.tabs.remove(tabs[0].id)\n"
    "    })\n"
    "  } else if (command === 'duplicate-tab') {\n"
    "    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {\n"
    "      if (tabs[0]?.url) chrome.tabs.create({ url: tabs[0].url })\n"
    "    })\n"
    "  }\n"
    "})\n\n"
    "chrome.runtime.onInstalled.addListener(() => {\n"
    "  console.log('Shortcut launcher installed')\n"
    "})\n"
)

CE09_CONTENT = "export {}\n"

examples.append(tokenize(build_conv("Build a Chrome extension for keyboard shortcuts to open Google, close tab, and duplicate tab", [
    ("project_init", {"name": "shortcut-launcher"}, "Created extension 'shortcut-launcher'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
    ("file_write", {"path": "src/popup/App.tsx", "content": CE09_POPUP}, "Written."),
    ("file_write", {"path": "src/background/service-worker.ts", "content": CE09_BG}, "Written."),
    ("file_write", {"path": "src/content/content.ts", "content": CE09_CONTENT}, "Written."),
    ("shell_exec", {"command": "cd deliverables/shortcut-launcher && npm run build"}, "Build successful. dist/ ready."),
    ("message_result", {"text": "Shortcut launcher ready. Configure in chrome://extensions/shortcuts. Commands: open Google, close tab, duplicate tab."}, "Delivered."),
])))

# ─────────────────────────────────────────────────────────────────────────────
# CE10: Context menu items (chrome.contextMenus + messaging)
# ─────────────────────────────────────────────────────────────────────────────

CE10_POPUP = (
    "import { useState, useEffect } from 'react'\n\n"
    "type SavedItem = { text: string; url: string; time: number }\n\n"
    "export default function App() {\n"
    "  const [items, setItems] = useState<SavedItem[]>([])\n\n"
    "  useEffect(() => {\n"
    "    chrome.storage.local.get(['saved'], r => setItems(r.saved || []))\n"
    "  }, [])\n\n"
    "  const clear = () => {\n"
    "    chrome.storage.local.set({ saved: [] })\n"
    "    setItems([])\n"
    "  }\n\n"
    "  return (\n"
    "    <div style={{padding:'12px',minWidth:'320px',maxHeight:'400px',overflow:'auto'}}>\n"
    "      <div style={{display:'flex',justifyContent:'space-between',marginBottom:'8px'}}>\n"
    "        <h3 style={{margin:0}}>Saved Text ({items.length})</h3>\n"
    "        <button onClick={clear}>Clear</button>\n"
    "      </div>\n"
    "      {items.length === 0 && <p style={{color:'#999'}}>Right-click text to save it</p>}\n"
    "      {items.map((item, i) => (\n"
    "        <div key={i} style={{borderBottom:'1px solid #eee',padding:'6px 0',fontSize:'13px'}}>\n"
    "          <div style={{fontStyle:'italic'}}>'{item.text}'</div>\n"
    "          <div style={{color:'#666',fontSize:'11px'}}>{item.url}</div>\n"
    "        </div>\n"
    "      ))}\n"
    "    </div>\n"
    "  )\n"
    "}\n"
)

CE10_BG = (
    "chrome.runtime.onInstalled.addListener(() => {\n"
    "  chrome.contextMenus.create({\n"
    "    id: 'save-selection',\n"
    "    title: 'Save selected text',\n"
    "    contexts: ['selection'],\n"
    "  })\n"
    "  chrome.contextMenus.create({\n"
    "    id: 'copy-link',\n"
    "    title: 'Copy link to clipboard',\n"
    "    contexts: ['link'],\n"
    "  })\n"
    "})\n\n"
    "chrome.contextMenus.onClicked.addListener((info, tab) => {\n"
    "  if (info.menuItemId === 'save-selection' && info.selectionText) {\n"
    "    chrome.storage.local.get(['saved'], r => {\n"
    "      const saved = r.saved || []\n"
    "      saved.unshift({ text: info.selectionText!.slice(0, 200), url: tab?.url || '', time: Date.now() })\n"
    "      chrome.storage.local.set({ saved: saved.slice(0, 50) })\n"
    "    })\n"
    "  }\n"
    "  if (info.menuItemId === 'copy-link' && tab?.id) {\n"
    "    chrome.tabs.sendMessage(tab.id, { type: 'copy', text: info.linkUrl })\n"
    "  }\n"
    "})\n"
)

CE10_CONTENT = (
    "chrome.runtime.onMessage.addListener((msg) => {\n"
    "  if (msg.type === 'copy') {\n"
    "    navigator.clipboard.writeText(msg.text || '').catch(() => {})\n"
    "  }\n"
    "})\n\n"
    "export {}\n"
)

examples.append(tokenize(build_conv("Build a Chrome extension with context menu items to save selected text and copy links", [
    ("project_init", {"name": "context-saver"}, "Created extension 'context-saver'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
    ("file_write", {"path": "src/popup/App.tsx", "content": CE10_POPUP}, "Written."),
    ("file_write", {"path": "src/background/service-worker.ts", "content": CE10_BG}, "Written."),
    ("file_write", {"path": "src/content/content.ts", "content": CE10_CONTENT}, "Written."),
    ("shell_exec", {"command": "cd deliverables/context-saver && npm run build"}, "Build successful. dist/ ready."),
    ("message_result", {"text": "Context saver ready. Right-click text to save, right-click links to copy. View saved items in popup."}, "Delivered."),
])))

# ─────────────────────────────────────────────────────────────────────────────
# CE11: Download tracker (chrome.downloads API)
# ─────────────────────────────────────────────────────────────────────────────

CE11_POPUP = (
    "import { useState, useEffect } from 'react'\n\n"
    "type DLItem = { filename: string; url: string; fileSize: number; startTime: string }\n\n"
    "export default function App() {\n"
    "  const [downloads, setDownloads] = useState<DLItem[]>([])\n\n"
    "  useEffect(() => {\n"
    "    chrome.storage.local.get(['downloads'], r => setDownloads(r.downloads || []))\n"
    "  }, [])\n\n"
    "  const fmt = (bytes: number) => bytes > 1e6 ? (bytes/1e6).toFixed(1)+'MB' : (bytes/1e3).toFixed(0)+'KB'\n\n"
    "  return (\n"
    "    <div style={{padding:'12px',minWidth:'360px',maxHeight:'480px',overflow:'auto'}}>\n"
    "      <h3 style={{margin:'0 0 8px'}}>Recent Downloads ({downloads.length})</h3>\n"
    "      {downloads.length === 0 && <p style={{color:'#999'}}>No downloads yet</p>}\n"
    "      {downloads.map((d, i) => (\n"
    "        <div key={i} style={{borderBottom:'1px solid #eee',padding:'6px 0'}}>\n"
    "          <div style={{fontWeight:'bold',fontSize:'13px'}}>{d.filename.split('/').pop()}</div>\n"
    "          <div style={{color:'#666',fontSize:'11px'}}>{fmt(d.fileSize)} &bull; {new Date(d.startTime).toLocaleTimeString()}</div>\n"
    "        </div>\n"
    "      ))}\n"
    "    </div>\n"
    "  )\n"
    "}\n"
)

CE11_BG = (
    "chrome.downloads.onCreated.addListener((downloadItem) => {\n"
    "  chrome.storage.local.get(['downloads'], r => {\n"
    "    const downloads = r.downloads || []\n"
    "    downloads.unshift({\n"
    "      filename: downloadItem.filename,\n"
    "      url: downloadItem.url,\n"
    "      fileSize: downloadItem.fileSize || 0,\n"
    "      startTime: downloadItem.startTime,\n"
    "    })\n"
    "    chrome.storage.local.set({ downloads: downloads.slice(0, 100) })\n"
    "  })\n"
    "})\n\n"
    "chrome.runtime.onInstalled.addListener(() => {\n"
    "  chrome.storage.local.set({ downloads: [] })\n"
    "})\n"
)

CE11_CONTENT = "export {}\n"

examples.append(tokenize(build_conv("Build a Chrome extension that tracks all downloads and shows them in a popup", [
    ("project_init", {"name": "download-tracker"}, "Created extension 'download-tracker'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
    ("file_write", {"path": "src/popup/App.tsx", "content": CE11_POPUP}, "Written."),
    ("file_write", {"path": "src/background/service-worker.ts", "content": CE11_BG}, "Written."),
    ("file_write", {"path": "src/content/content.ts", "content": CE11_CONTENT}, "Written."),
    ("shell_exec", {"command": "cd deliverables/download-tracker && npm run build"}, "Build successful. dist/ ready."),
    ("message_result", {"text": "Download tracker ready. Every new download appears in the popup with filename, size, and time."}, "Delivered."),
])))

# ─────────────────────────────────────────────────────────────────────────────
# CE12: Reading mode toggle (content script + messaging)
# Injects a clean reading view by stripping ads and adjusting typography
# ─────────────────────────────────────────────────────────────────────────────

CE12_POPUP = (
    "import { useState } from 'react'\n\n"
    "export default function App() {\n"
    "  const [active, setActive] = useState(false)\n\n"
    "  const toggle = () => {\n"
    "    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {\n"
    "      if (tabs[0]?.id) {\n"
    "        chrome.tabs.sendMessage(tabs[0].id, { type: 'toggle-reading-mode' })\n"
    "        setActive(a => !a)\n"
    "      }\n"
    "    })\n"
    "  }\n\n"
    "  return (\n"
    "    <div style={{padding:'16px',minWidth:'200px',textAlign:'center'}}>\n"
    "      <h3>Reading Mode</h3>\n"
    "      <button\n"
    "        onClick={toggle}\n"
    "        style={{padding:'8px 24px',background:active?'#4caf50':'#2196f3',color:'#fff',border:'none',borderRadius:'4px',cursor:'pointer',fontSize:'14px'}}\n"
    "      >\n"
    "        {active ? 'Disable' : 'Enable'}\n"
    "      </button>\n"
    "    </div>\n"
    "  )\n"
    "}\n"
)

CE12_BG = (
    "chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {\n"
    "  sendResponse({ ok: true })\n"
    "})\n\n"
    "chrome.runtime.onInstalled.addListener(() => {\n"
    "  console.log('Reading mode extension installed')\n"
    "})\n"
)

CE12_CONTENT = (
    "let readingMode = false\n\n"
    "chrome.runtime.onMessage.addListener((msg) => {\n"
    "  if (msg.type === 'toggle-reading-mode') {\n"
    "    readingMode = !readingMode\n"
    "    applyReadingMode(readingMode)\n"
    "  }\n"
    "})\n\n"
    "function applyReadingMode(active: boolean) {\n"
    "  const existing = document.getElementById('__reading_mode_style')\n"
    "  if (active) {\n"
    "    const style = document.createElement('style')\n"
    "    style.id = '__reading_mode_style'\n"
    "    style.textContent = [\n"
    "      'body { max-width: 680px !important; margin: 0 auto !important; padding: 20px !important; }',\n"
    "      'body * { font-family: Georgia, serif !important; font-size: 18px !important; line-height: 1.8 !important; }',\n"
    "      'aside, nav, footer, .sidebar, .ads, [class*=\"ad\"], [id*=\"ad\"] { display: none !important; }'\n"
    "    ].join('\\n')\n"
    "    document.head.appendChild(style)\n"
    "  } else if (existing) {\n"
    "    existing.remove()\n"
    "  }\n"
    "}\n\n"
    "export {}\n"
)

examples.append(tokenize(build_conv("Build a Chrome extension that toggles reading mode on any webpage", [
    ("project_init", {"name": "reading-mode"}, "Created extension 'reading-mode'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."),
    ("file_write", {"path": "src/popup/App.tsx", "content": CE12_POPUP}, "Written."),
    ("file_write", {"path": "src/background/service-worker.ts", "content": CE12_BG}, "Written."),
    ("file_write", {"path": "src/content/content.ts", "content": CE12_CONTENT}, "Written."),
    ("shell_exec", {"command": "cd deliverables/reading-mode && npm run build"}, "Build successful. dist/ ready."),
    ("message_result", {"text": "Reading mode ready. Click the extension icon and press Enable to apply clean typography and hide sidebars/ads."}, "Delivered."),
])))


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
out = Path(OUT_PATH)
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w") as f:
    for ex in examples:
        f.write(json.dumps(ex) + "\n")
print(f"Wrote {len(examples)} examples to {out}")

# Combine v1+v2+v3
prev_paths = [
    "workspace/training_data/chrome_ext_sft_v1.jsonl",
    "workspace/training_data/chrome_ext_sft_v2.jsonl",
]
combined = Path(COMBINED_PATH)
total = 0
with open(combined, "w") as cf:
    for p in prev_paths:
        lines = Path(p).read_text().splitlines()
        for line in lines:
            if line.strip():
                cf.write(line + "\n")
                total += 1
    for line in out.read_text().splitlines():
        if line.strip():
            cf.write(line + "\n")
            total += 1
print(f"Combined: {total} examples -> {combined}")
print(f"  v1(4) + v2(4) + v3({len(examples)}) = {total}")
