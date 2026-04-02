# Realtime Template

React 19 + TypeScript + Vite + WebSocket server. For chat apps, live dashboards, multiplayer.

## Pre-built Components

Import from `./components`:
- `useWebSocket({ url?, onMessage?, reconnect? })` — auto-connect, auto-reconnect, typed messages

Returns: `{ connected, send, lastMessage }`

Backend (server/index.js):
- WebSocket server on port 3001
- Auto-tracks connected clients
- Broadcasts messages to all clients
- Health check at GET /api/health

## Build Loop

1. Write `src/App.tsx` FIRST with `import "./index.css"`
2. Use `useWebSocket` hook for real-time communication
3. Customize `server/index.js` for your message types
4. `npx vite build` to compile-check

## Usage Example

```tsx
import { useWebSocket } from "./components"

function Chat() {
  const [messages, setMessages] = useState<string[]>([])
  const { connected, send, lastMessage } = useWebSocket({
    onMessage: (data) => {
      if (data.type === "chat") setMessages(prev => [...prev, data.text])
    }
  })

  return (
    <div className="container">
      <div>{connected ? "🟢 Connected" : "🔴 Disconnected"}</div>
      <div className="card" style={{ height: 400, overflow: "auto" }}>
        {messages.map((m, i) => <div key={i}>{m}</div>)}
      </div>
      <input onKeyDown={e => {
        if (e.key === "Enter") {
          send({ type: "chat", text: e.currentTarget.value })
          e.currentTarget.value = ""
        }
      }} placeholder="Type a message..." />
    </div>
  )
}
```

## Server Message Format

```js
// Client sends:
{ type: "chat", text: "hello" }

// Server broadcasts to all:
{ type: "chat", text: "hello" }

// Server auto-sends:
{ type: "connected", clients: 3 }
{ type: "clients", count: 3 }
```

## File Structure

```
src/
  App.tsx                  ← Wire your app here
  components/
    useWebSocket.ts        ← WebSocket hook (ready to use)
    index.ts
server/
  index.js                 ← WebSocket + Express server (customize)
```
