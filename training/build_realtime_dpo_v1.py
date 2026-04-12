#!/usr/bin/env python3
"""Realtime DPO pairs v1 — targeting L4 Hack-Free failures for realtime adapter.

RTF01: realtime template param — project_init(template="realtime") not project_init(name)
RTF02: server-first — file_write(server/index.js) before file_write(src/App.tsx)
RTF03: useWebSocket not fetch — use useWebSocket hook, never fetch() polling
RTF04: undertow before deliver — undertow QA before message_result
RTF05: ws library — WebSocketServer from 'ws', not socket.io
RTF06: no-main.tsx — never overwrite main.tsx/vite.config.ts after project_init

Usage:
  /usr/bin/python3 training/build_realtime_dpo_v1.py
  Output: workspace/training_data/realtime_dpo_v1.jsonl
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

SYSTEM = (
    "You are Tsunami. You are the wave. You build apps by calling tools.\n\n"
    "The ocean:\n"
    "- current: your sense of direction. If uncertain, search first.\n"
    "- circulation: routing. Low tension=deliver. High tension=search or refuse.\n"
    "- pressure: sustained uncertainty. 2 failures=search. 4 failures=ask the user.\n"
    "- eddies: parallel workers. 3+ components=dispatch swell.\n"
    "- undertow: QA. ALWAYS verify before delivering.\n"
    "- break: compile. shell_exec build after EVERY file_write.\n"
    "- reef: error. Fix directly. Type/syntax -> file_edit. Missing module -> shell_exec npm install. "
    "Missing file -> file_write. Wrong path (cd fails) -> shell_exec with corrected path (NEVER message_chat). "
    "CSS resolution errors -> file_edit to remove/replace the import.\n\n"
    "REALTIME PIPELINE (WebSocket apps follow this EXACTLY):\n"
    "1. project_init(name, template='realtime')\n"
    "2. file_write(server/index.js) -- WebSocketServer with rooms/history/presence\n"
    "3. file_write(src/App.tsx) -- useWebSocket hook + ChatFeed + ChatInput + PresenceDot\n"
    "4. shell_exec -- npm run build\n"
    "5. IF ERROR: fix directly\n"
    "6. undertow -- QA before delivery\n"
    "7. message_result -- land the wave\n\n"
    "REALTIME RULES:\n"
    "- ALWAYS template='realtime' in project_init\n"
    "- ALWAYS write server/index.js BEFORE src/App.tsx\n"
    "- ALWAYS use useWebSocket hook — NEVER fetch() for real-time data\n"
    "- ALWAYS use ws library (WebSocketServer from 'ws') — NOT socket.io\n"
    "- NEVER overwrite main.tsx, vite.config.ts, or index.css\n"
    "- NEVER skip undertow before message_result\n\n"
    "NEVER skip the break. NEVER deliver without building. One tool call per response. Be brief."
)

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file with full content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Make targeted modifications to an existing file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "plan_update", "description": "Create or revise the task plan.", "parameters": {"type": "object", "properties": {"goal": {"type": "string"}, "phases": {"type": "array"}}, "required": ["goal", "phases"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_read", "description": "Read a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
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

# ──────────────────────────────────────────────────────────────────────────────
# RTF01: realtime template param — project_init must include template="realtime"
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, prompt) in enumerate([
    ("chat-app",      "Build a multi-room chat app with presence indicators"),
    ("live-poll",     "Build a real-time voting and live polling app"),
    ("collab-todos",  "Build a collaborative todo app with live sync across users"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="project_init", chosen_args={"name": app, "template": "realtime"},
        rejected_fn="project_init", rejected_args={"name": app},
        source_bug="RTF01-realtime-template",
        note=f"rtf01-{i+1}: project_init must include template='realtime' for websocket apps",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# RTF02: server-first — file_write server/index.js before src/App.tsx
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, server_snippet) in enumerate([
    ("chat-app",     "const wss = new WebSocketServer({ port: 3001 });"),
    ("live-poll",    "const wss = new WebSocketServer({ port: 3001 }); const polls = {};"),
    ("typing-chat",  "const wss = new WebSocketServer({ port: 3001 }); const typingUsers = new Set();"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Build a realtime {app.replace('-', ' ')}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init",
                "arguments": json.dumps({"name": app, "template": "realtime"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}' with template='realtime'. Write server/index.js then src/App.tsx."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "server/index.js", "content": server_snippet},
        rejected_fn="file_write", rejected_args={"path": "src/App.tsx", "content": "// App component"},
        source_bug="RTF02-server-first",
        note=f"rtf02-{i+1}: after project_init with realtime template, server/index.js FIRST not App.tsx",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# RTF03: useWebSocket not fetch — always use WebSocket hook, never fetch() polling
# ──────────────────────────────────────────────────────────────────────────────
_WS_APP_CODE = '''import { useWebSocket } from './lib/useWebSocket';
import { ChatFeed } from './components/ChatFeed';
import { ChatInput } from './components/ChatInput';

export default function App() {
  const { messages, sendMessage, connected } = useWebSocket({
    url: "ws://localhost:3001",
    onMessage: (msg) => console.log(msg),
  });
  return (
    <div className="app">
      <ChatFeed messages={messages} />
      <ChatInput onSend={sendMessage} disabled={!connected} />
    </div>
  );
}'''

_FETCH_APP_CODE = '''export default function App() {
  const [messages, setMessages] = React.useState([]);
  React.useEffect(() => {
    const poll = setInterval(() => {
      fetch("/api/messages").then(r => r.json()).then(setMessages);
    }, 1000);
    return () => clearInterval(poll);
  }, []);
  return <div>{messages.map(m => <div key={m.id}>{m.text}</div>)}</div>;
}'''

for i, (app, prompt) in enumerate([
    ("chat-app",      "Build a live chat app"),
    ("live-feed",     "Build a live activity feed that updates in real time"),
    ("presence-app",  "Build an app that shows who is online"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init",
                "arguments": json.dumps({"name": app, "template": "realtime"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}'. Write server/index.js then src/App.tsx."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write",
                "arguments": json.dumps({"path": "server/index.js", "content": "const wss = new WebSocketServer({ port: 3001 });"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c2",
         "content": "[file_write] server/index.js written."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "src/App.tsx", "content": _WS_APP_CODE},
        rejected_fn="file_write", rejected_args={"path": "src/App.tsx", "content": _FETCH_APP_CODE},
        source_bug="RTF03-useWebSocket-not-fetch",
        note=f"rtf03-{i+1}: App.tsx must use useWebSocket hook not fetch() polling",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# RTF04: undertow before message_result — always QA before delivering
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, build_out) in enumerate([
    ("chat-app",    "dist/index.html"),
    ("live-poll",   "dist/index.html"),
    ("collab-todos","dist/index.html"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Build a realtime {app.replace('-', ' ')}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init",
                "arguments": json.dumps({"name": app, "template": "realtime"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}'."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write",
                "arguments": json.dumps({"path": "server/index.js", "content": "const wss = new WebSocketServer({ port: 3001 });"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c2",
         "content": "[file_write] server/index.js written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "file_write",
                "arguments": json.dumps({"path": "src/App.tsx", "content": _WS_APP_CODE})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c3",
         "content": "[file_write] src/App.tsx written."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c4", "type": "function", "function": {
                "name": "shell_exec",
                "arguments": json.dumps({"command": "npm run build"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c4",
         "content": "[shell_exec] Build succeeded. dist/index.html ready."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="undertow", chosen_args={"path": build_out},
        rejected_fn="message_result", rejected_args={"text": f"{app} is ready with real-time features."},
        source_bug="RTF04-undertow-before-deliver",
        note=f"rtf04-{i+1}: after successful build, undertow QA BEFORE message_result",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# RTF05: ws library — use WebSocketServer from 'ws', not socket.io
# ──────────────────────────────────────────────────────────────────────────────
_WS_SERVER = '''import { WebSocketServer } from 'ws';

const wss = new WebSocketServer({ port: 3001 });
const rooms = {};

wss.on('connection', (ws) => {
  ws.on('message', (data) => {
    const msg = JSON.parse(data);
    if (msg.type === 'join') {
      ws.room = msg.room;
      if (!rooms[msg.room]) rooms[msg.room] = new Set();
      rooms[msg.room].add(ws);
    } else if (msg.type === 'message') {
      const payload = JSON.stringify({ type: 'message', text: msg.text, from: msg.from });
      rooms[ws.room]?.forEach(client => client.readyState === 1 && client.send(payload));
    }
  });
  ws.on('close', () => rooms[ws.room]?.delete(ws));
});'''

_SOCKETIO_SERVER = '''import { Server } from 'socket.io';
import { createServer } from 'http';

const httpServer = createServer();
const io = new Server(httpServer, { cors: { origin: "*" } });

io.on('connection', (socket) => {
  socket.on('join', (room) => socket.join(room));
  socket.on('message', (data) => io.to(data.room).emit('message', data));
});
httpServer.listen(3001);'''

for i, (app, prompt) in enumerate([
    ("chat-app",       "Build a real-time multi-room chat app"),
    ("live-collab",    "Build a collaborative whiteboard with live sync"),
    ("presence-board", "Build an app with live presence and online status"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init",
                "arguments": json.dumps({"name": app, "template": "realtime"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}' with template='realtime'. Write server/index.js."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "server/index.js", "content": _WS_SERVER},
        rejected_fn="file_write", rejected_args={"path": "server/index.js", "content": _SOCKETIO_SERVER},
        source_bug="RTF05-ws-not-socketio",
        note=f"rtf05-{i+1}: server/index.js must use 'ws' library WebSocketServer not socket.io",
    ))

# ──────────────────────────────────────────────────────────────────────────────
# RTF06: no main.tsx overwrite — only write server/index.js and src/App.tsx,
#        never file_write(main.tsx) or file_write(vite.config.ts)
# ──────────────────────────────────────────────────────────────────────────────
for i, (app, prompt) in enumerate([
    ("chat-app",    "Build a real-time chat app with rooms"),
    ("live-votes",  "Build a live voting app with real-time results"),
    ("sync-notes",  "Build a collaborative notes app with live sync"),
]):
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "project_init",
                "arguments": json.dumps({"name": app, "template": "realtime"})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c1",
         "content": f"[project_init] Created '{app}' with template='realtime'. Write server/index.js then src/App.tsx."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "file_write",
                "arguments": json.dumps({"path": "server/index.js", "content": _WS_SERVER})
            }}
        ]},
        {"role": "tool", "tool_call_id": "c2",
         "content": "[file_write] server/index.js written successfully."},
    ]
    PAIRS.append(make_pair(
        msgs,
        chosen_fn="file_write", chosen_args={"path": "src/App.tsx", "content": _WS_APP_CODE},
        rejected_fn="file_write", rejected_args={"path": "src/main.tsx", "content": "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App';\nReactDOM.createRoot(document.getElementById('root')!).render(<App/>);"},
        source_bug="RTF06-no-main-tsx",
        note=f"rtf06-{i+1}: after server/index.js, write src/App.tsx not src/main.tsx (scaffold already has main.tsx)",
    ))


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
OUT_PATH = Path("workspace/training_data/realtime_dpo_v1.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_PATH, "w") as f:
    for p in PAIRS:
        f.write(json.dumps(p) + "\n")

counts = {
    "rtf01-template":     sum(1 for p in PAIRS if "rtf01" in p["note"]),
    "rtf02-server-first": sum(1 for p in PAIRS if "rtf02" in p["note"]),
    "rtf03-ws-not-fetch": sum(1 for p in PAIRS if "rtf03" in p["note"]),
    "rtf04-undertow":     sum(1 for p in PAIRS if "rtf04" in p["note"]),
    "rtf05-ws-lib":       sum(1 for p in PAIRS if "rtf05" in p["note"]),
    "rtf06-no-main-tsx":  sum(1 for p in PAIRS if "rtf06" in p["note"]),
}
print(f"\n=== REALTIME DPO v1 SUMMARY ===")
print(f"  Total pairs: {len(PAIRS)}")
print(f"  File: {OUT_PATH}")
for k, v in counts.items():
    print(f"  {k}: {v}")
print(f"\nTo train (after SFT realtime-v1 + merge):")
print(f"  # Step 1: SFT")
print(f"  /usr/bin/python3 training/train_unsloth.py --model google/gemma-4-e4b-it \\")
print(f"    --data workspace/training_data/realtime_sft_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-realtime-v1 --epochs 3 --lora-r 16 --lr 2e-4")
print(f"  # Step 2: Merge")
print(f"  /usr/bin/python3 training/merge_adapter.py --base google/gemma-4-e4b-it \\")
print(f"    --adapter models/gemma-4-e4b-tsunami-realtime-v1 \\")
print(f"    --output models/gemma-4-e4b-tsunami-realtime-v1-merged")
print(f"  # Step 3: DPO")
print(f"  /usr/bin/python3 training/train_dpo.py \\")
print(f"    --base-model models/gemma-4-e4b-tsunami-realtime-v1-merged \\")
print(f"    --data workspace/training_data/realtime_dpo_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-realtime-v2 --epochs 1 --lora-r 16 --lr 5e-6 --beta 0.1")
