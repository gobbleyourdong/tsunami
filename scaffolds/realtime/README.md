# Realtime Scaffold

Vite + React 19 + WebSocket server with rooms, history, and presence.

## Quick Start
- `npm run dev` — starts Vite + WebSocket server concurrently
- Server: `ws://localhost:3001`
- Frontend: `http://localhost:5173`

## Server Features (server/index.js)
- **Rooms**: clients join rooms, messages stay within the room
- **History**: last 100 messages per room, sent on join
- **Presence**: live user count per room
- **Usernames**: `set_username` message type

### Message Types (client → server)
```json
{"type": "message", "text": "hello"}
{"type": "join", "room": "general"}
{"type": "set_username", "username": "alice"}
```

### Message Types (server → client)
```json
{"type": "connected", "room": "lobby", "username": "user-a1b2", "history": [...], "users": 3}
{"type": "message", "text": "hello", "username": "alice", "timestamp": 1234567890}
{"type": "presence", "users": 3}
{"type": "joined", "room": "general", "history": [...], "users": 2}
```

## Components (import from `./components`)

### useWebSocket
```tsx
const { connected, send, lastMessage } = useWebSocket({
  url: "ws://localhost:3001",
  onMessage: (data) => console.log(data)
})
send({ type: "message", text: "hello" })
```

### ChatFeed
`<ChatFeed messages={messages} currentUser="alice" />`
- Auto-scrolls, chat bubbles (mine right, theirs left), system messages

### ChatInput
`<ChatInput onSend={text => send({type:"message", text})} />`

### PresenceDot
`<PresenceDot connected={connected} userCount={5} />`

## CSS Classes
- `.chat-layout`, `.chat-sidebar`, `.chat-main` — sidebar + feed layout
- `.chat-feed`, `.chat-bubble.mine/.theirs` — message bubbles
- `.chat-input-bar` — input + send button
- `.room-item`, `.room-item.active` — room list in sidebar
- `.presence`, `.presence-dot.online/.offline` — connection indicator
- `.live-feed`, `.live-feed-item` — for event/notification feeds
