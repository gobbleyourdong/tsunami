#!/usr/bin/env python3
"""Realtime adapter SFT v1 — 6 examples using the realtime scaffold.

Scaffold: Vite + React + WebSocket server (ws library) with rooms, history, presence.
Components: useWebSocket, ChatFeed, ChatInput, PresenceDot, Modal, Toast.
Pipeline: project_init(template="realtime") → server/index.js → src/App.tsx → build → undertow → deliver.

Usage:
  /usr/bin/python3 training/build_realtime_v1.py
  Output: workspace/training_data/realtime_sft_v1.jsonl
"""
import json
from datetime import date
from pathlib import Path

print("Loading tokenizer (google/gemma-4-e4b-it)...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

RT_SYSTEM = """You are Tsunami. You are the wave. You build real-time apps by calling tools.

## Realtime Pipeline (every build follows this EXACTLY)

1. project_init(name, template="realtime") -- create project from realtime scaffold
2. file_write(server/index.js) -- WebSocket server with rooms and message handlers
3. file_write(src/App.tsx) -- React frontend using useWebSocket hook
4. shell_exec -- run npm run build
5. IF ERROR: fix directly with file_edit
6. undertow -- QA before delivery
7. message_result -- land the wave

## WebSocket Message Protocol

Client → Server:
  {"type": "message", "text": "hello"}
  {"type": "join", "room": "general"}
  {"type": "set_username", "username": "alice"}

Server → Client:
  {"type": "connected", "room": "lobby", "username": "user-abc", "history": [...], "users": 3}
  {"type": "message", "text": "hello", "username": "alice", "timestamp": 1234567890}
  {"type": "presence", "users": 3}

## Available Components

useWebSocket: const { connected, send, lastMessage } = useWebSocket({ url: 'ws://localhost:3001', onMessage })
ChatFeed: <ChatFeed messages={msgs} currentUser="alice" />
ChatInput: <ChatInput onSend={text => send({type:"message",text})} />
PresenceDot: <PresenceDot connected={connected} userCount={userCount} />

## Rules
- NEVER use fetch() or REST endpoints for real-time data -- use WebSocket send/receive
- ALWAYS write server/index.js BEFORE src/App.tsx
- server/index.js uses 'ws' library (WebSocketServer from 'ws')
- NEVER overwrite main.tsx, vite.config.ts, or index.css
- One tool call per response. Be brief.
"""

RT_TOOLS = [
    {"type": "function", "function": {"name": "project_init", "description": "Create a project.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "template": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "description": "Write a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "description": "Edit a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "undertow", "description": "QA test an HTML file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "message_result", "description": "Deliver final outcome.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "description": "Talk to the user.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
]

RT01_SERVER = """\
import { createServer } from "http"
import { WebSocketServer } from "ws"

const PORT = process.env.PORT || 3001
const server = createServer()
const wss = new WebSocketServer({ server })

const rooms = new Map()
const history = new Map()
const clientMeta = new Map()

function getRoom(name) {
  if (!rooms.has(name)) { rooms.set(name, new Set()); history.set(name, []) }
  return rooms.get(name)
}

function broadcast(room, data, exclude = null) {
  const msg = JSON.stringify(data)
  const clients = rooms.get(room)
  if (!clients) return
  for (const c of clients) {
    if (c !== exclude && c.readyState === 1) c.send(msg)
  }
}

const ROOMS = ["general", "random", "dev"]

wss.on("connection", (ws) => {
  const username = `user-${Math.random().toString(36).slice(2, 6)}`
  clientMeta.set(ws, { room: "general", username })
  const room = getRoom("general")
  room.add(ws)
  ws.send(JSON.stringify({
    type: "connected", room: "general", username,
    history: (history.get("general") || []).slice(-50),
    users: room.size, rooms: ROOMS,
  }))
  broadcast("general", { type: "presence", users: room.size }, ws)

  ws.on("message", (raw) => {
    try {
      const msg = JSON.parse(raw.toString())
      const meta = clientMeta.get(ws)
      if (msg.type === "set_username") {
        meta.username = msg.username
        ws.send(JSON.stringify({ type: "username_set", username: meta.username }))
      } else if (msg.type === "join") {
        const oldRoom = rooms.get(meta.room)
        if (oldRoom) { oldRoom.delete(ws); broadcast(meta.room, { type: "presence", users: oldRoom.size }) }
        meta.room = msg.room
        const newRoom = getRoom(msg.room)
        newRoom.add(ws)
        ws.send(JSON.stringify({
          type: "connected", room: msg.room, username: meta.username,
          history: (history.get(msg.room) || []).slice(-50),
          users: newRoom.size, rooms: ROOMS,
        }))
        broadcast(msg.room, { type: "presence", users: newRoom.size }, ws)
      } else if (msg.type === "message") {
        const entry = { type: "message", text: msg.text, username: meta.username, timestamp: Date.now() }
        const hist = history.get(meta.room) || []
        hist.push(entry)
        if (hist.length > 100) hist.shift()
        history.set(meta.room, hist)
        broadcast(meta.room, entry)
        ws.send(JSON.stringify(entry))
      }
    } catch {}
  })

  ws.on("close", () => {
    const meta = clientMeta.get(ws)
    if (meta) {
      const room = rooms.get(meta.room)
      if (room) { room.delete(ws); broadcast(meta.room, { type: "presence", users: room.size }) }
    }
    clientMeta.delete(ws)
  })
})

server.listen(PORT, () => console.log(`WS server on :${PORT}`))
"""

RT01_APP = """\
import "./index.css"
import { useState, useCallback } from "react"
import { useWebSocket } from "./components/useWebSocket"
import ChatFeed from "./components/ChatFeed"
import ChatInput from "./components/ChatInput"
import PresenceDot from "./components/PresenceDot"

interface Message {
  type: string
  text: string
  username: string
  timestamp: number
}

const ROOMS = ["general", "random", "dev"]

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [userCount, setUserCount] = useState(0)
  const [currentUser, setCurrentUser] = useState("")
  const [currentRoom, setCurrentRoom] = useState("general")
  const [username, setUsername] = useState("")
  const [showUsernameModal, setShowUsernameModal] = useState(true)

  const onMessage = useCallback((data: any) => {
    if (data.type === "connected") {
      setCurrentUser(data.username)
      setCurrentRoom(data.room)
      setUserCount(data.users)
      if (data.history?.length) setMessages(data.history)
    } else if (data.type === "message") {
      setMessages(prev => [...prev, data])
    } else if (data.type === "presence") {
      setUserCount(data.users)
    }
  }, [])

  const { connected, send } = useWebSocket({ url: "ws://localhost:3001", onMessage })

  const setName = () => {
    if (!username.trim()) return
    send({ type: "set_username", username })
    setCurrentUser(username)
    setShowUsernameModal(false)
  }

  const joinRoom = (room: string) => {
    send({ type: "join", room })
    setCurrentRoom(room)
    setMessages([])
  }

  return (
    <div className="flex min-h-screen bg-0">
      {/* Sidebar */}
      <aside className="w-52 bg-1 border-r border-white/5 flex flex-col">
        <div className="p-4 border-b border-white/5">
          <PresenceDot connected={connected} userCount={userCount} />
          <p className="text-xs text-muted mt-2 truncate">{currentUser}</p>
        </div>
        <div className="p-3">
          <p className="text-xs text-muted uppercase tracking-wider mb-2">Rooms</p>
          {ROOMS.map(room => (
            <button
              key={room}
              onClick={() => joinRoom(room)}
              className={`w-full text-left px-3 py-2 rounded text-sm ${currentRoom === room ? "room-item active" : "room-item"}`}
            >#{room}</button>
          ))}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col">
        <div className="border-b border-white/5 p-4 flex items-center justify-between">
          <h2 className="font-semibold">#{currentRoom}</h2>
          <span className="text-xs text-muted">{userCount} online</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <ChatFeed messages={messages} currentUser={currentUser} />
        </div>
        <div className="p-4 border-t border-white/5">
          <ChatInput onSend={text => send({ type: "message", text })} disabled={!connected} />
        </div>
      </div>

      {/* Username modal */}
      {showUsernameModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-2 rounded-xl p-8 w-80 shadow-2xl">
            <h2 className="text-lg font-bold mb-4">Choose a username</h2>
            <input
              className="w-full bg-1 border border-white/10 rounded px-3 py-2 text-sm mb-4 focus:outline-none focus:border-accent"
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={e => e.key === "Enter" && setName()}
              placeholder="Enter username..."
              autoFocus
            />
            <button className="w-full button primary" onClick={setName}>Join Chat</button>
          </div>
        </div>
      )}
    </div>
  )
}
"""

RT02_SERVER = """\
import { createServer } from "http"
import { WebSocketServer } from "ws"

const PORT = process.env.PORT || 3001
const server = createServer()
const wss = new WebSocketServer({ server })

// Live poll state
const polls = new Map() // poll_id → {question, options: [{text, votes}]}
const clientMeta = new Map()

let nextPollId = 1

wss.on("connection", (ws) => {
  const username = `voter-${Math.random().toString(36).slice(2, 6)}`
  clientMeta.set(ws, { username, voted: new Set() })

  // Send all current polls on join
  ws.send(JSON.stringify({
    type: "init",
    username,
    polls: Array.from(polls.entries()).map(([id, p]) => ({ id, ...p })),
  }))

  ws.on("message", (raw) => {
    try {
      const msg = JSON.parse(raw.toString())
      const meta = clientMeta.get(ws)

      if (msg.type === "create_poll") {
        const id = nextPollId++
        const poll = {
          question: msg.question,
          options: (msg.options || []).map(t => ({ text: t, votes: 0 })),
          createdBy: meta.username,
        }
        polls.set(id, poll)
        broadcast({ type: "poll_created", id, ...poll })
      } else if (msg.type === "vote") {
        if (meta.voted.has(msg.poll_id)) return
        const poll = polls.get(msg.poll_id)
        if (!poll || msg.option_index >= poll.options.length) return
        poll.options[msg.option_index].votes++
        meta.voted.add(msg.poll_id)
        broadcast({ type: "poll_updated", id: msg.poll_id, options: poll.options })
      }
    } catch {}
  })

  ws.on("close", () => clientMeta.delete(ws))
})

function broadcast(data) {
  const msg = JSON.stringify(data)
  for (const c of wss.clients) {
    if (c.readyState === 1) c.send(msg)
  }
}

server.listen(PORT, () => console.log(`WS poll server on :${PORT}`))
"""

RT02_APP = """\
import "./index.css"
import { useState, useCallback } from "react"
import { useWebSocket } from "./components/useWebSocket"
import PresenceDot from "./components/PresenceDot"

interface PollOption { text: string; votes: number }
interface Poll { id: number; question: string; options: PollOption[]; createdBy: string }

export default function App() {
  const [polls, setPolls] = useState<Poll[]>([])
  const [currentUser, setCurrentUser] = useState("")
  const [voted, setVoted] = useState<Set<number>>(new Set())
  const [question, setQuestion] = useState("")
  const [options, setOptions] = useState(["", ""])

  const onMessage = useCallback((data: any) => {
    if (data.type === "init") {
      setCurrentUser(data.username)
      setPolls(data.polls || [])
    } else if (data.type === "poll_created") {
      setPolls(prev => [...prev, data])
    } else if (data.type === "poll_updated") {
      setPolls(prev => prev.map(p => p.id === data.id ? { ...p, options: data.options } : p))
    }
  }, [])

  const { connected, send } = useWebSocket({ url: "ws://localhost:3001", onMessage })

  const createPoll = () => {
    if (!question.trim() || options.filter(o => o.trim()).length < 2) return
    send({ type: "create_poll", question, options: options.filter(o => o.trim()) })
    setQuestion("")
    setOptions(["", ""])
  }

  const vote = (pollId: number, optionIndex: number) => {
    if (voted.has(pollId)) return
    send({ type: "vote", poll_id: pollId, option_index: optionIndex })
    setVoted(prev => new Set([...prev, pollId]))
  }

  return (
    <div className="min-h-screen bg-0 p-8 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Live Polls</h1>
        <PresenceDot connected={connected} userCount={0} />
      </div>

      {/* Create poll */}
      <div className="card p-6 mb-8">
        <h2 className="text-lg font-semibold mb-4">Create a Poll</h2>
        <input
          className="w-full bg-1 border border-white/10 rounded px-3 py-2 text-sm mb-3 focus:outline-none focus:border-accent"
          value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask a question..."
        />
        {options.map((opt, i) => (
          <input key={i} className="w-full bg-1 border border-white/10 rounded px-3 py-2 text-sm mb-2 focus:outline-none focus:border-accent"
            value={opt} onChange={e => { const o = [...options]; o[i] = e.target.value; setOptions(o) }}
            placeholder={`Option ${i + 1}`}
          />
        ))}
        <div className="flex gap-3 mt-3">
          <button className="button ghost text-sm" onClick={() => setOptions(o => [...o, ""])}>+ Option</button>
          <button className="button primary text-sm" onClick={createPoll}>Create Poll</button>
        </div>
      </div>

      {/* Polls list */}
      <div className="space-y-4">
        {polls.map(poll => {
          const totalVotes = poll.options.reduce((s, o) => s + o.votes, 0)
          const hasVoted = voted.has(poll.id)
          return (
            <div key={poll.id} className="card p-6">
              <h3 className="font-semibold mb-4">{poll.question}</h3>
              <div className="space-y-2">
                {poll.options.map((opt, idx) => {
                  const pct = totalVotes > 0 ? Math.round(opt.votes / totalVotes * 100) : 0
                  return (
                    <button
                      key={idx}
                      onClick={() => !hasVoted && vote(poll.id, idx)}
                      disabled={hasVoted}
                      className="w-full text-left relative overflow-hidden rounded p-3 border border-white/10 hover:border-accent/50 disabled:cursor-default"
                    >
                      <div className="absolute inset-0 bg-accent/10" style={{ width: `${pct}%` }} />
                      <div className="relative flex justify-between text-sm">
                        <span>{opt.text}</span>
                        <span className="text-muted">{opt.votes} ({pct}%)</span>
                      </div>
                    </button>
                  )
                })}
              </div>
              <p className="text-xs text-muted mt-3">{totalVotes} votes · by {poll.createdBy}</p>
            </div>
          )
        })}
        {polls.length === 0 && <p className="text-muted text-center py-12">No polls yet. Create one above.</p>}
      </div>
    </div>
  )
}
"""

# RT03: Error recovery — using fetch() instead of WebSocket → fix with file_edit
RT03_BROKEN_APP = """\
import "./index.css"
import { useState, useEffect } from "react"

interface Notification {
  id: number
  text: string
  type: string
}

export default function App() {
  const [notifications, setNotifications] = useState<Notification[]>([])

  useEffect(() => {
    // Wrong: polling with fetch instead of WebSocket
    const interval = setInterval(() => {
      fetch('/api/notifications').then(r => r.json()).then(setNotifications)
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="p-8">
      {notifications.map(n => <div key={n.id}>{n.text}</div>)}
    </div>
  )
}
"""

RT03_FIXED_APP = """\
import "./index.css"
import { useState, useCallback } from "react"
import { useWebSocket } from "./components/useWebSocket"
import PresenceDot from "./components/PresenceDot"

interface Notification {
  id: number
  text: string
  type: "info" | "success" | "warning" | "error"
  timestamp: number
}

export default function App() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [connected, setConnected] = useState(false)

  const onMessage = useCallback((data: any) => {
    if (data.type === "notification") {
      setNotifications(prev => [data, ...prev].slice(0, 50))
    } else if (data.type === "connected") {
      setConnected(true)
      if (data.history) setNotifications(data.history)
    }
  }, [])

  const { connected: wsConnected, send } = useWebSocket({ url: "ws://localhost:3001", onMessage })

  const dismiss = (id: number) => setNotifications(prev => prev.filter(n => n.id !== id))

  return (
    <div className="min-h-screen bg-0 p-8 max-w-xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Live Notifications</h1>
        <PresenceDot connected={wsConnected} userCount={0} />
      </div>
      <div className="space-y-2">
        {notifications.map(n => (
          <div key={n.id} className={`card p-4 flex items-start gap-3 border-l-4 ${
            n.type === 'success' ? 'border-green-500' :
            n.type === 'warning' ? 'border-yellow-500' :
            n.type === 'error' ? 'border-red-500' : 'border-accent'
          }`}>
            <div className="flex-1">
              <p className="text-sm">{n.text}</p>
              <p className="text-xs text-muted mt-1">{new Date(n.timestamp).toLocaleTimeString()}</p>
            </div>
            <button className="text-muted hover:text-white text-xs" onClick={() => dismiss(n.id)}>✕</button>
          </div>
        ))}
        {notifications.length === 0 && (
          <div className="text-center text-muted py-16">
            <p>Waiting for notifications...</p>
          </div>
        )}
      </div>
    </div>
  )
}
"""

RT03_SERVER = """\
import { createServer } from "http"
import { WebSocketServer } from "ws"

const PORT = process.env.PORT || 3001
const server = createServer()
const wss = new WebSocketServer({ server })

const history = []

// Emit a sample notification every 5 seconds
const SAMPLES = [
  { text: "New user signed up", type: "success" },
  { text: "Server CPU at 78%", type: "warning" },
  { text: "Payment processed: $99", type: "success" },
  { text: "API rate limit reached", type: "error" },
  { text: "Deployment started", type: "info" },
  { text: "Backup completed", type: "success" },
]

let idx = 0
setInterval(() => {
  const entry = { ...SAMPLES[idx % SAMPLES.length], id: Date.now(), timestamp: Date.now(), type: "notification" }
  idx++
  history.push(entry)
  if (history.length > 50) history.shift()
  broadcast(entry)
}, 5000)

function broadcast(data) {
  const msg = JSON.stringify(data)
  for (const c of wss.clients) { if (c.readyState === 1) c.send(msg) }
}

wss.on("connection", (ws) => {
  ws.send(JSON.stringify({ type: "connected", history: history.slice(-20) }))
})

server.listen(PORT, () => console.log(`WS notification server on :${PORT}`))
"""


def tc(id, name, args):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}

def tr(tool_call_id, content):
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}

def atc(id, name, args):
    return {"role": "assistant", "content": "", "tool_calls": [tc(id, name, args)]}

def tokenize(messages):
    return tokenizer.apply_chat_template(
        messages, tools=RT_TOOLS, tokenize=False, add_generation_prompt=False
    )


examples = []

# RT01: Multi-room chat
examples.append(tokenize([
    {"role": "system", "content": RT_SYSTEM},
    {"role": "user", "content": "Build a multi-room live chat app with general, random, and dev channels"},
    atc("c1", "project_init", {"name": "live-chat", "template": "realtime"}),
    tr("c1", "[project_init] Created 'live-chat' from realtime scaffold. Write server/index.js then src/App.tsx."),
    atc("c2", "file_write", {"path": "server/index.js", "content": RT01_SERVER}),
    tr("c2", "[file_write] server/index.js written."),
    atc("c3", "file_write", {"path": "src/App.tsx", "content": RT01_APP}),
    tr("c3", "[file_write] src/App.tsx written."),
    atc("c4", "shell_exec", {"command": "cd deliverables/live-chat && npm run build"}),
    tr("c4", "[shell_exec] Build succeeded. dist/ ready."),
    atc("c5", "undertow", {"path": "deliverables/live-chat/dist/index.html"}),
    tr("c5", "[undertow] PASS: page loads, chat layout renders, input visible."),
    atc("c6", "message_result", {"text": "Multi-room live chat ready. Three channels: #general, #random, #dev. Pick a username on first connect, then switch rooms from the sidebar. Messages broadcast in real-time within each room."}),
]))

# RT02: Live polls
examples.append(tokenize([
    {"role": "system", "content": RT_SYSTEM},
    {"role": "user", "content": "Build a live polling app where users can create polls and vote in real-time"},
    atc("c1", "project_init", {"name": "live-polls", "template": "realtime"}),
    tr("c1", "[project_init] Created 'live-polls' from realtime scaffold. Write server/index.js then src/App.tsx."),
    atc("c2", "file_write", {"path": "server/index.js", "content": RT02_SERVER}),
    tr("c2", "[file_write] server/index.js written."),
    atc("c3", "file_write", {"path": "src/App.tsx", "content": RT02_APP}),
    tr("c3", "[file_write] src/App.tsx written."),
    atc("c4", "shell_exec", {"command": "cd deliverables/live-polls && npm run build"}),
    tr("c4", "[shell_exec] Build succeeded. dist/ ready."),
    atc("c5", "undertow", {"path": "deliverables/live-polls/dist/index.html"}),
    tr("c5", "[undertow] PASS: page loads, poll creation form visible."),
    atc("c6", "message_result", {"text": "Live polling app ready. Create polls with multiple options, vote once per poll, see results update instantly as others vote. Powered by WebSocket — no refresh needed."}),
]))

# RT03: Error recovery — fetch() polling → file_edit to useWebSocket
examples.append(tokenize([
    {"role": "system", "content": RT_SYSTEM},
    {"role": "user", "content": "Build a live notification feed that streams server events in real-time"},
    atc("c1", "project_init", {"name": "notif-feed", "template": "realtime"}),
    tr("c1", "[project_init] Created 'notif-feed' from realtime scaffold. Write server/index.js then src/App.tsx."),
    atc("c2", "file_write", {"path": "server/index.js", "content": RT03_SERVER}),
    tr("c2", "[file_write] server/index.js written."),
    atc("c3", "file_write", {"path": "src/App.tsx", "content": RT03_BROKEN_APP}),
    tr("c3", "[file_write] src/App.tsx written."),
    atc("c4", "shell_exec", {"command": "cd deliverables/notif-feed && npm run build"}),
    tr("c4", "[shell_exec] Warning: fetch('/api/notifications') will fail — this is a WebSocket-only server. Use useWebSocket hook instead of fetch polling."),
    atc("c5", "file_edit", {
        "path": "src/App.tsx",
        "old_text": RT03_BROKEN_APP,
        "new_text": RT03_FIXED_APP,
    }),
    tr("c5", "[file_edit] src/App.tsx updated."),
    atc("c6", "shell_exec", {"command": "cd deliverables/notif-feed && npm run build"}),
    tr("c6", "[shell_exec] Build succeeded. dist/ ready."),
    atc("c7", "undertow", {"path": "deliverables/notif-feed/dist/index.html"}),
    tr("c7", "[undertow] PASS: page loads, notification feed renders, WebSocket connection established."),
    atc("c8", "message_result", {"text": "Live notification feed ready. Server emits alerts every 5 seconds (new signups, warnings, payments, deployments). Color-coded by severity. Dismiss individual notifications. Powered by WebSocket — no polling."}),
]))

# RT04: Simple typing indicator chat (simpler server, exercise ChatFeed + ChatInput)
RT04_SERVER = """\
import { createServer } from "http"
import { WebSocketServer } from "ws"

const PORT = process.env.PORT || 3001
const server = createServer()
const wss = new WebSocketServer({ server })
const clientMeta = new Map()
const history = []
const typing = new Set()

function broadcast(data, exclude = null) {
  const msg = JSON.stringify(data)
  for (const c of wss.clients) {
    if (c !== exclude && c.readyState === 1) c.send(msg)
  }
}

wss.on("connection", (ws) => {
  const username = `user-${Math.random().toString(36).slice(2, 5)}`
  clientMeta.set(ws, username)
  ws.send(JSON.stringify({ type: "connected", username, history: history.slice(-50), users: wss.clients.size }))
  broadcast({ type: "presence", users: wss.clients.size }, ws)

  ws.on("message", (raw) => {
    try {
      const msg = JSON.parse(raw.toString())
      const uname = clientMeta.get(ws)
      if (msg.type === "set_username") {
        clientMeta.set(ws, msg.username)
      } else if (msg.type === "message") {
        typing.delete(uname)
        const entry = { type: "message", text: msg.text, username: uname, timestamp: Date.now() }
        history.push(entry)
        if (history.length > 100) history.shift()
        broadcast(entry)
        ws.send(JSON.stringify(entry))
        broadcast({ type: "typing", users: [...typing] })
      } else if (msg.type === "typing") {
        typing.add(uname)
        broadcast({ type: "typing", users: [...typing] }, ws)
        setTimeout(() => { typing.delete(uname); broadcast({ type: "typing", users: [...typing] }) }, 3000)
      }
    } catch {}
  })

  ws.on("close", () => {
    const uname = clientMeta.get(ws)
    clientMeta.delete(ws)
    typing.delete(uname)
    broadcast({ type: "presence", users: wss.clients.size })
    broadcast({ type: "typing", users: [...typing] })
  })
})

server.listen(PORT, () => console.log(`WS chat on :${PORT}`))
"""

RT04_APP = """\
import "./index.css"
import { useState, useCallback } from "react"
import { useWebSocket } from "./components/useWebSocket"
import ChatFeed from "./components/ChatFeed"
import ChatInput from "./components/ChatInput"
import PresenceDot from "./components/PresenceDot"

interface Message {
  type: string
  text: string
  username: string
  timestamp: number
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [currentUser, setCurrentUser] = useState("")
  const [userCount, setUserCount] = useState(0)
  const [typingUsers, setTypingUsers] = useState<string[]>([])

  const onMessage = useCallback((data: any) => {
    if (data.type === "connected") {
      setCurrentUser(data.username)
      setUserCount(data.users)
      if (data.history) setMessages(data.history)
    } else if (data.type === "message") {
      setMessages(prev => [...prev, data])
    } else if (data.type === "presence") {
      setUserCount(data.users)
    } else if (data.type === "typing") {
      setTypingUsers((data.users || []).filter((u: string) => u !== currentUser))
    }
  }, [currentUser])

  const { connected, send } = useWebSocket({ url: "ws://localhost:3001", onMessage })

  const handleSend = (text: string) => send({ type: "message", text })
  const handleTyping = () => send({ type: "typing" })

  return (
    <div className="flex flex-col min-h-screen bg-0 max-w-2xl mx-auto">
      <header className="border-b border-white/5 p-4 flex items-center justify-between">
        <h1 className="font-bold text-lg">Live Chat</h1>
        <PresenceDot connected={connected} userCount={userCount} />
      </header>
      <div className="flex-1 overflow-hidden">
        <ChatFeed messages={messages} currentUser={currentUser} typingUsers={typingUsers} />
      </div>
      <div className="p-4 border-t border-white/5">
        <ChatInput onSend={handleSend} disabled={!connected} />
      </div>
    </div>
  )
}
"""

examples.append(tokenize([
    {"role": "system", "content": RT_SYSTEM},
    {"role": "user", "content": "Build a live chat app with typing indicators and online presence"},
    atc("c1", "project_init", {"name": "typing-chat", "template": "realtime"}),
    tr("c1", "[project_init] Created 'typing-chat' from realtime scaffold. Write server/index.js then src/App.tsx."),
    atc("c2", "file_write", {"path": "server/index.js", "content": RT04_SERVER}),
    tr("c2", "[file_write] server/index.js written."),
    atc("c3", "file_write", {"path": "src/App.tsx", "content": RT04_APP}),
    tr("c3", "[file_write] src/App.tsx written."),
    atc("c4", "shell_exec", {"command": "cd deliverables/typing-chat && npm run build"}),
    tr("c4", "[shell_exec] Build succeeded. dist/ ready."),
    atc("c5", "undertow", {"path": "deliverables/typing-chat/dist/index.html"}),
    tr("c5", "[undertow] PASS: page loads, chat feed visible, input active."),
    atc("c6", "message_result", {"text": "Live chat ready with typing indicators and presence. ChatFeed shows message bubbles with avatars, 'user is typing...' indicator bounces when others are active. Online count updates as users connect."}),
]))

# RT05: Collaborative todo (custom message types)
RT05_SERVER = """\
import { createServer } from "http"
import { WebSocketServer } from "ws"

const PORT = process.env.PORT || 3001
const server = createServer()
const wss = new WebSocketServer({ server })

// Shared todo list state
let todos = []
let nextId = 1

function broadcast(data) {
  const msg = JSON.stringify(data)
  for (const c of wss.clients) { if (c.readyState === 1) c.send(msg) }
}

wss.on("connection", (ws) => {
  const user = `user-${Math.random().toString(36).slice(2, 5)}`
  ws.send(JSON.stringify({ type: "init", todos, user, users: wss.clients.size }))
  broadcast({ type: "presence", users: wss.clients.size })

  ws.on("message", (raw) => {
    try {
      const msg = JSON.parse(raw.toString())
      if (msg.type === "add_todo") {
        const todo = { id: nextId++, text: msg.text, done: false, author: user }
        todos.push(todo)
        broadcast({ type: "todo_added", todo })
      } else if (msg.type === "toggle_todo") {
        const t = todos.find(t => t.id === msg.id)
        if (t) { t.done = !t.done; broadcast({ type: "todo_updated", todo: t }) }
      } else if (msg.type === "delete_todo") {
        todos = todos.filter(t => t.id !== msg.id)
        broadcast({ type: "todo_deleted", id: msg.id })
      }
    } catch {}
  })

  ws.on("close", () => broadcast({ type: "presence", users: wss.clients.size }))
})

server.listen(PORT, () => console.log(`WS collab todos on :${PORT}`))
"""

RT05_APP = """\
import "./index.css"
import { useState, useCallback } from "react"
import { useWebSocket } from "./components/useWebSocket"
import PresenceDot from "./components/PresenceDot"

interface Todo { id: number; text: string; done: boolean; author: string }

export default function App() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [input, setInput] = useState("")
  const [currentUser, setCurrentUser] = useState("")
  const [userCount, setUserCount] = useState(0)

  const onMessage = useCallback((data: any) => {
    if (data.type === "init") {
      setTodos(data.todos); setCurrentUser(data.user); setUserCount(data.users)
    } else if (data.type === "todo_added") {
      setTodos(prev => [...prev, data.todo])
    } else if (data.type === "todo_updated") {
      setTodos(prev => prev.map(t => t.id === data.todo.id ? data.todo : t))
    } else if (data.type === "todo_deleted") {
      setTodos(prev => prev.filter(t => t.id !== data.id))
    } else if (data.type === "presence") {
      setUserCount(data.users)
    }
  }, [])

  const { connected, send } = useWebSocket({ url: "ws://localhost:3001", onMessage })

  const add = () => {
    if (!input.trim()) return
    send({ type: "add_todo", text: input })
    setInput("")
  }

  return (
    <div className="min-h-screen bg-0 p-8 max-w-lg mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Collaborative Todos</h1>
        <PresenceDot connected={connected} userCount={userCount} />
      </div>
      <div className="flex gap-2 mb-6">
        <input
          className="flex-1 bg-1 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-accent"
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && add()} placeholder="Add a task..."
        />
        <button className="button primary text-sm" onClick={add}>Add</button>
      </div>
      <div className="space-y-2">
        {todos.map(t => (
          <div key={t.id} className="card flex items-center gap-3 p-3">
            <input type="checkbox" checked={t.done} onChange={() => send({ type: "toggle_todo", id: t.id })} className="w-4 h-4" />
            <span className={`flex-1 text-sm ${t.done ? "line-through text-muted" : ""}`}>{t.text}</span>
            <span className="text-xs text-muted">{t.author}</span>
            <button className="text-muted hover:text-red-400 text-xs" onClick={() => send({ type: "delete_todo", id: t.id })}>✕</button>
          </div>
        ))}
        {todos.length === 0 && <p className="text-muted text-center py-8">No tasks yet.</p>}
      </div>
    </div>
  )
}
"""

examples.append(tokenize([
    {"role": "system", "content": RT_SYSTEM},
    {"role": "user", "content": "Build a collaborative todo list where all users see changes in real-time"},
    atc("c1", "project_init", {"name": "collab-todos", "template": "realtime"}),
    tr("c1", "[project_init] Created 'collab-todos' from realtime scaffold. Write server/index.js then src/App.tsx."),
    atc("c2", "file_write", {"path": "server/index.js", "content": RT05_SERVER}),
    tr("c2", "[file_write] server/index.js written."),
    atc("c3", "file_write", {"path": "src/App.tsx", "content": RT05_APP}),
    tr("c3", "[file_write] src/App.tsx written."),
    atc("c4", "shell_exec", {"command": "cd deliverables/collab-todos && npm run build"}),
    tr("c4", "[shell_exec] Build succeeded. dist/ ready."),
    atc("c5", "undertow", {"path": "deliverables/collab-todos/dist/index.html"}),
    tr("c5", "[undertow] PASS: page loads, todo list visible, add input working."),
    atc("c6", "message_result", {"text": "Collaborative todo list ready. All connected users see todos update instantly — add, check off, and delete tasks synced across everyone. Author tag shows who added each task. Online count in the top right."}),
]))

# RT06: Conversational routing
examples.append(tokenize([
    {"role": "system", "content": RT_SYSTEM},
    {"role": "user", "content": "Can a realtime app have multiple WebSocket connections on the same page?"},
    {"role": "assistant", "content": "Yes — each useWebSocket call creates an independent WebSocket connection. You can have multiple hooks pointing to the same or different servers. Each connection has its own connected state, send function, and message handler. Just keep in mind that each connection holds a socket, so for most apps one connection is sufficient; use multiple only when you genuinely need separate channels.", "tool_calls": []},
]))

# Output
OUT_PATH = Path("workspace/training_data/realtime_sft_v1.jsonl")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, "w") as f:
    for ex in examples:
        f.write(json.dumps({"text": ex, "date": TODAY, "adapter": "realtime-v1"}) + "\n")

print(f"\nWrote {len(examples)} examples to {OUT_PATH}")
for name in ["RT01 multi-room chat", "RT02 live polls", "RT03 error recovery (fetch→WebSocket)",
             "RT04 typing indicators + presence", "RT05 collaborative todos", "RT06 conversational"]:
    print(f"  {name}")
print(f"\nTrain: python training/train_unsloth.py --model google/gemma-4-e4b-it --data {OUT_PATH} --output models/gemma-4-e4b-tsunami-realtime-v1 --epochs 3 --lora-r 16 --lr 2e-4")
