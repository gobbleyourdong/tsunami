# Realtime Scaffold

Vite + React 19 + WebSocket server with rooms, history, and presence.
Inherits the Tsunami design system (Plus Jakarta Sans, surface hierarchy).

## Quick Start
- `npm run dev` — starts Vite + WebSocket server concurrently
- Server: `ws://localhost:3001`
- Frontend: `http://localhost:5173`

## Server Features (server/index.js)
- **Rooms**: clients join rooms, messages stay within the room
- **History**: last 100 messages per room, sent on join
- **Presence**: live user count per room
- **Usernames**: `set_username` message type

### Message Protocol
```json
// Client → Server
{"type": "message", "text": "hello"}
{"type": "join", "room": "general"}
{"type": "set_username", "username": "alice"}

// Server → Client
{"type": "connected", "room": "lobby", "username": "user-a1b2", "history": [...], "users": 3}
{"type": "message", "text": "hello", "username": "alice", "timestamp": 1234567890}
{"type": "presence", "users": 3}
```

## Components (import from `./components/ComponentName`)

| Component | Usage |
|-----------|-------|
| **useWebSocket** | `const { connected, send, lastMessage } = useWebSocket({ url, onMessage })` — Hook with auto-reconnect |
| **ChatFeed** | `<ChatFeed messages={msgs} currentUser="alice" typingUsers={["bob"]} />` — Auto-scroll, avatar initials, typing indicator with bouncing dots |
| **ChatInput** | `<ChatInput onSend={text => send({type:"message", text})} />` — Enter to send, disabled state |
| **PresenceDot** | `<PresenceDot connected={connected} userCount={5} />` — Status dot with glow |
| **Modal** | `<Modal open={show} onClose={close} title="Settings" size="md">` — Escape close, blur backdrop |
| **Toast** | `toast("Connected!", "success")` + `<ToastContainer />` — 4 types with icons |

## Chat CSS Classes
- `.chat-layout`, `.chat-sidebar`, `.chat-main` — sidebar + feed layout
- `.chat-feed`, `.chat-bubble.mine/.theirs` — message bubbles with tail
- `.chat-input-bar` — input + send button
- `.chat-name`, `.chat-time`, `.chat-system` — message metadata
- `.room-item`, `.room-item.active` — room list with accent highlight
- `.status-dot.online/.offline/.busy` — presence indicators with glow
- `.live-feed`, `.live-feed-item` — event/notification feeds
- `.avatar` — circle with initials or image

## Hooks (import from `./hooks`)
- `useLocalStorage(key, initial)` — persist username, room preference
- `useDebounce(value, delay)` — debounce search/filter

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- Use the WebSocket message protocol — don't invent new types
- Use CSS classes for styling — avoid inline styles
