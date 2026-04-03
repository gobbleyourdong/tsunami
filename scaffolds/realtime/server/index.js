import express from "express"
import { createServer } from "http"
import { WebSocketServer } from "ws"

const PORT = process.env.PORT || 3001
const app = express()
const server = createServer(app)
const wss = new WebSocketServer({ server })

// Rooms — clients join rooms, messages broadcast within rooms
const rooms = new Map()  // room name → Set of ws clients
const history = new Map() // room name → last 100 messages
const clientMeta = new Map() // ws → { room, username }

function getRoom(name) {
  if (!rooms.has(name)) { rooms.set(name, new Set()); history.set(name, []) }
  return rooms.get(name)
}

function broadcastToRoom(room, data, exclude = null) {
  const msg = JSON.stringify(data)
  const clients = rooms.get(room)
  if (!clients) return
  for (const client of clients) {
    if (client !== exclude && client.readyState === 1) client.send(msg)
  }
}

function broadcastAll(data) {
  const msg = JSON.stringify(data)
  for (const client of wss.clients) {
    if (client.readyState === 1) client.send(msg)
  }
}

wss.on("connection", (ws) => {
  clientMeta.set(ws, { room: "lobby", username: `user-${Math.random().toString(36).slice(2, 6)}` })

  // Auto-join lobby
  const lobby = getRoom("lobby")
  lobby.add(ws)

  ws.send(JSON.stringify({
    type: "connected",
    room: "lobby",
    username: clientMeta.get(ws).username,
    history: (history.get("lobby") || []).slice(-50),
    users: lobby.size,
  }))

  broadcastToRoom("lobby", { type: "presence", users: lobby.size }, ws)

  ws.on("message", (raw) => {
    try {
      const msg = JSON.parse(raw.toString())
      const meta = clientMeta.get(ws)

      switch (msg.type) {
        case "join": {
          // Leave current room
          const oldRoom = rooms.get(meta.room)
          if (oldRoom) { oldRoom.delete(ws); broadcastToRoom(meta.room, { type: "presence", users: oldRoom.size }) }
          // Join new room
          meta.room = msg.room || "lobby"
          const newRoom = getRoom(meta.room)
          newRoom.add(ws)
          ws.send(JSON.stringify({
            type: "joined", room: meta.room,
            history: (history.get(meta.room) || []).slice(-50),
            users: newRoom.size,
          }))
          broadcastToRoom(meta.room, { type: "presence", users: newRoom.size }, ws)
          break
        }

        case "message": {
          const payload = {
            type: "message",
            text: String(msg.text || "").slice(0, 2000),
            username: meta.username,
            room: meta.room,
            timestamp: Date.now(),
          }
          // Store in history (max 100 per room)
          const hist = history.get(meta.room) || []
          hist.push(payload)
          if (hist.length > 100) hist.shift()
          history.set(meta.room, hist)
          // Broadcast to room
          broadcastToRoom(meta.room, payload)
          break
        }

        case "set_username": {
          meta.username = String(msg.username || "").slice(0, 30) || meta.username
          ws.send(JSON.stringify({ type: "username_set", username: meta.username }))
          break
        }

        default:
          // Pass through — for custom message types
          broadcastToRoom(meta.room, { ...msg, username: meta.username })
      }
    } catch (e) {
      ws.send(JSON.stringify({ type: "error", message: "Invalid JSON" }))
    }
  })

  ws.on("close", () => {
    const meta = clientMeta.get(ws)
    if (meta) {
      const room = rooms.get(meta.room)
      if (room) { room.delete(ws); broadcastToRoom(meta.room, { type: "presence", users: room.size }) }
    }
    clientMeta.delete(ws)
  })
})

// REST endpoints
app.get("/api/health", (req, res) => res.json({ ok: true, clients: wss.clients.size }))
app.get("/api/rooms", (req, res) => {
  const list = []
  for (const [name, clients] of rooms) {
    list.push({ name, users: clients.size, messages: (history.get(name) || []).length })
  }
  res.json(list)
})

server.listen(PORT, () => console.log(`WebSocket: ws://localhost:${PORT}`))
