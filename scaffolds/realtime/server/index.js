import express from "express"
import { createServer } from "http"
import { WebSocketServer } from "ws"

const PORT = process.env.PORT || 3001
const app = express()
const server = createServer(app)
const wss = new WebSocketServer({ server })

// Track connected clients
const clients = new Set()

wss.on("connection", (ws) => {
  clients.add(ws)
  console.log(`Client connected (${clients.size} total)`)

  // Send welcome message
  ws.send(JSON.stringify({ type: "connected", clients: clients.size }))

  // Broadcast client count to all
  broadcast({ type: "clients", count: clients.size })

  ws.on("message", (raw) => {
    try {
      const msg = JSON.parse(raw.toString())
      // Echo to all clients (customize this for your app)
      broadcast(msg)
    } catch (e) {
      ws.send(JSON.stringify({ type: "error", message: "Invalid JSON" }))
    }
  })

  ws.on("close", () => {
    clients.delete(ws)
    broadcast({ type: "clients", count: clients.size })
    console.log(`Client disconnected (${clients.size} total)`)
  })
})

function broadcast(data) {
  const msg = JSON.stringify(data)
  for (const client of clients) {
    if (client.readyState === 1) client.send(msg)
  }
}

// Health check
app.get("/api/health", (req, res) => res.json({ ok: true, clients: clients.size }))

server.listen(PORT, () => console.log(`WebSocket server on ws://localhost:${PORT}`))
