#!/usr/bin/env python3
"""Chrome Extension DPO pairs v1 -- targeting likely L4 failures.

Based on eval_chrome_ext.py L4 scenarios (CEF01-CEF05):
  CEF01: After project_init -> first file_write MUST be popup path (not background)
  CEF02: Popup file_write MUST use chrome.* API (not raw fetch to external URL)
  CEF03: After successful build -> message_result (NOT undertow -- no headless for extensions)
  CEF04: TS build error -> file_edit NOT message_chat
  CEF05: After popup file_write -> next file_write MUST be background (not content first)

3 DPO pairs per pattern = 15 pairs total.

Usage:
  python training/build_chrome_ext_dpo_v1.py
  Output: workspace/training_data/chrome_ext_dpo_v1.jsonl
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

EXT_SYSTEM = """You are Tsunami. You are the wave. You build Chrome extensions by calling tools.

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

## Rules
- Write popup FIRST, then background, then content.
- NEVER call undertow -- extensions don't have HTTP servers to test.
- TS errors -> file_edit directly, not message_chat.
- One tool call per response. Be brief."""

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a Chrome extension project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Create or overwrite a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA-test an HTML file in headless browser.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
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

    return {
        "prompt": prompt_text,
        "chosen": chosen_response,
        "rejected": rejected_response,
        "images": [],
        "source_bug": source_bug,
        "note": note,
        "date": TODAY,
    }


PAIRS = []

POPUP_CONTENT = (
    "import { useState } from 'react'\n"
    "export default function App() {\n"
    "  const [count, setCount] = useState(0)\n"
    "  return <div><span>{count}</span><button onClick={() => setCount(c => c+1)}>+</button></div>\n"
    "}\n"
)
BG_CONTENT = "chrome.runtime.onInstalled.addListener(() => { console.log('installed') })\n"
CONTENT_TS = "export {}\n"

# ─────────────────────────────────────────────────────────────────────────────
# CEF01: After project_init -> first file_write MUST be popup (src/popup/App.tsx)
# Model failure mode: writes background/service-worker.ts first
# ─────────────────────────────────────────────────────────────────────────────
for i, (ext_name, user_msg) in enumerate([
    ("tab-counter", "Build a Chrome extension that counts open tabs"),
    ("word-counter", "Build a Chrome extension that counts words on the current page"),
    ("bookmark-saver", "Build a Chrome extension for quick bookmarks"),
]):
    msgs = [
        {"role": "system", "content": EXT_SYSTEM},
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": ext_name})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created extension '{ext_name}'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "src/popup/App.tsx", "content": POPUP_CONTENT},
        rejected_fn="file_write",
        rejected_args={"path": "src/background/service-worker.ts", "content": BG_CONTENT},
        source_bug="CEF01-popup-first",
        note=f"popup-first-{i+1}: after project_init, write popup/App.tsx BEFORE background",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# CEF02: Popup file_write MUST use chrome.* API (not raw fetch to external URL)
# Model failure mode: writes popup that uses fetch("https://external.api/...") to read tabs
# ─────────────────────────────────────────────────────────────────────────────
CHROME_API_POPUP = (
    "import { useState, useEffect } from 'react'\n"
    "export default function App() {\n"
    "  const [count, setCount] = useState(0)\n"
    "  useEffect(() => {\n"
    "    chrome.tabs.query({}, tabs => setCount(tabs.length))\n"
    "  }, [])\n"
    "  return <div>{count} tabs open</div>\n"
    "}\n"
)
RAW_FETCH_POPUP = (
    "import { useState, useEffect } from 'react'\n"
    "export default function App() {\n"
    "  const [data, setData] = useState(null)\n"
    "  useEffect(() => {\n"
    "    fetch('https://api.example.com/tabs').then(r => r.json()).then(setData)\n"
    "  }, [])\n"
    "  return <div>{JSON.stringify(data)}</div>\n"
    "}\n"
)

for i, (ext_name, user_msg) in enumerate([
    ("tab-counter", "Build a Chrome extension that shows the number of open tabs"),
    ("active-page", "Build a Chrome extension that shows the current page title"),
    ("tab-list", "Build a Chrome extension popup that lists all open tabs"),
]):
    msgs = [
        {"role": "system", "content": EXT_SYSTEM},
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": ext_name})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created extension '{ext_name}'. Write popup/App.tsx first."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "src/popup/App.tsx", "content": CHROME_API_POPUP},
        rejected_fn="file_write",
        rejected_args={"path": "src/popup/App.tsx", "content": RAW_FETCH_POPUP},
        source_bug="CEF02-chrome-api",
        note=f"chrome-api-{i+1}: popup must use chrome.tabs/chrome.storage, NOT raw fetch",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# CEF03: After successful build -> message_result (NOT undertow)
# Extensions run in Chrome, not HTTP server -- undertow cannot test them
# ─────────────────────────────────────────────────────────────────────────────
for i, (ext_name, user_msg) in enumerate([
    ("tab-counter", "Build a Chrome extension that shows tab count"),
    ("quick-notes", "Build a Chrome extension for quick notes"),
    ("dark-toggle", "Build a Chrome extension dark mode toggle"),
]):
    msgs = [
        {"role": "system", "content": EXT_SYSTEM},
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": ext_name})}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": f"[project_init] Created '{ext_name}'."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/popup/App.tsx", "content": POPUP_CONTENT})}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/background/service-worker.ts", "content": BG_CONTENT})}}
        ]},
        {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c4", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/content/content.ts", "content": CONTENT_TS})}}
        ]},
        {"role": "tool", "tool_call_id": "c4", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c5", "type": "function", "function": {
                "name": "shell_exec", "arguments": json.dumps({"command": f"cd deliverables/{ext_name} && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c5", "content": "[shell_exec] Build successful. dist/ ready."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="message_result",
        chosen_args={"text": f"{ext_name} extension ready. Load the dist/ folder as an unpacked extension in Chrome."},
        rejected_fn="undertow",
        rejected_args={"path": f"deliverables/{ext_name}/dist/index.html"},
        source_bug="CEF03-no-undertow",
        note=f"no-undertow-{i+1}: after ext build success -> message_result, NOT undertow",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# CEF04: TS build error -> file_edit NOT message_chat
# ─────────────────────────────────────────────────────────────────────────────
TS_ERRORS = [
    (
        "src/popup/App.tsx(8,15): error TS2345: Argument of type 'number' is not assignable to parameter of type 'string'.",
        "src/popup/App.tsx",
        "const [count, setCount] = useState(0)",
        "const [count, setCount] = useState<number>(0)",
    ),
    (
        "src/background/service-worker.ts(3,1): error TS2304: Cannot find name 'chrome'. Are you missing @types/chrome?",
        "src/background/service-worker.ts",
        "chrome.runtime.onInstalled",
        "// @ts-ignore\nchrome.runtime.onInstalled",
    ),
    (
        "src/content/content.ts(12,7): error TS2551: Property 'textContent' does not exist on type 'Element | null'.",
        "src/content/content.ts",
        "el.textContent",
        "(el as HTMLElement).textContent",
    ),
]

for i, (error_msg, file_path, old_text, new_text) in enumerate(TS_ERRORS):
    msgs = [
        {"role": "system", "content": EXT_SYSTEM},
        {"role": "user", "content": "Build a Chrome extension tab counter"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": "tab-counter"})}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": "[project_init] Created."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/popup/App.tsx", "content": POPUP_CONTENT})}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/background/service-worker.ts", "content": BG_CONTENT})}}
        ]},
        {"role": "tool", "tool_call_id": "c3", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c4", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/content/content.ts", "content": CONTENT_TS})}}
        ]},
        {"role": "tool", "tool_call_id": "c4", "content": "[file_write] Written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c5", "type": "function", "function": {
                "name": "shell_exec", "arguments": json.dumps({"command": "cd deliverables/tab-counter && npm run build"})}}
        ]},
        {"role": "tool", "tool_call_id": "c5", "content": f"[shell_exec] Error: {error_msg}"},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_edit",
        chosen_args={"path": file_path, "old_text": old_text, "new_text": new_text},
        rejected_fn="message_chat",
        rejected_args={"text": f"The build failed with: {error_msg[:80]}. Please check your TypeScript config.", "done": False},
        source_bug="CEF04-ts-error-file-edit",
        note=f"ts-error-{i+1}: TS build error -> file_edit fix, NOT message_chat",
    ))

# ─────────────────────────────────────────────────────────────────────────────
# CEF05: After popup write -> NEXT must be background (not content, not message_result)
# Order: popup -> background -> content -> build
# ─────────────────────────────────────────────────────────────────────────────
for i, (ext_name, user_msg) in enumerate([
    ("site-blocker", "Build a site blocker Chrome extension"),
    ("dark-mode", "Build a Chrome extension dark mode toggle"),
    ("page-notes", "Build a Chrome extension for per-page notes"),
]):
    msgs = [
        {"role": "system", "content": EXT_SYSTEM},
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init", "arguments": json.dumps({"name": ext_name})}}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{ext_name}'. Write popup/App.tsx, background/service-worker.ts, content/content.ts."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write", "arguments": json.dumps({"path": "src/popup/App.tsx", "content": POPUP_CONTENT})}}
        ]},
        {"role": "tool", "tool_call_id": "c2", "content": "[file_write] Written."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write",
        chosen_args={"path": "src/background/service-worker.ts", "content": BG_CONTENT},
        rejected_fn="file_write",
        rejected_args={"path": "src/content/content.ts", "content": CONTENT_TS},
        source_bug="CEF05-bg-before-content",
        note=f"bg-before-content-{i+1}: after popup write, next is background NOT content",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
output = Path("workspace/training_data/chrome_ext_dpo_v1.jsonl")
output.parent.mkdir(parents=True, exist_ok=True)
with open(output, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

print(f"\nWrote {len(PAIRS)} DPO pairs to {output}")
print("\nPairs by pattern:")
from collections import Counter
by_bug = Counter(p["source_bug"] for p in PAIRS)
for bug, count in sorted(by_bug.items()):
    print(f"  {bug}: {count}")
print(f"\nTotal: {len(PAIRS)} pairs")
