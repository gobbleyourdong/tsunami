# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Protocol](#protocol)
- [ ] [Server](#server)
- [ ] [Client](#client)
- [ ] [Reconnect](#reconnect)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
React (Vite) client + Express + `ws` server. Bundled scaffold:
- `server/index.js` — rooms (`Map<roomName, Set<ws>>`), per-room
  history, broadcast helper.
- `src/components/useWebSocket.ts` — connect, auto-reconnect (2s),
  JSON parse, `send(any)`, `connected` flag, `lastMessage` snapshot.

Target shape: live cursors, presence list, shared whiteboard,
chat-style toy. NOT a CRDT — last-write-wins for state changes;
broadcast-on-receive for events.

## Protocol
Pin a tagged-union message shape in BOTH client and server. The
bundled scaffold's wire format:
```ts
type Msg =
  | { type: "chat";     user: string; text: string; ts: number }
  | { type: "join";     user: string; room: string }
  | { type: "leave";    user: string; room: string }
  | { type: "presence"; users: string[] }
  | { type: "state";    payload: unknown }     // last-write-wins blob
```
Add app-specific variants (cursor positions, drawing strokes, etc.) as
new `type:` discriminators. Never change an existing variant's shape —
add a new variant if the surface needs to grow.

## Server
Customize `server/index.js`:
- On `connection`: parse `?room=<name>` from URL, add to room, broadcast `join`.
- On `message`: parse JSON, validate `type`, broadcast within room.
- On `close`: remove from room, broadcast `leave`.
- Optional: ring-buffer recent messages (last 100) per room and replay
  on join — lets reconnecting clients catch up.

Heartbeat: send `{ type: "ping" }` every 30s, expect `{ type: "pong" }`
back, drop the connection if no pong in 60s. Most casual realtime toys
skip this; add it if the goal mentions reliability.

## Client
Use `useWebSocket` from `src/components/useWebSocket.ts`:
```tsx
const { connected, send, lastMessage } = useWebSocket({
  url: `ws://localhost:3001?room=${room}`,
  onMessage: (m: Msg) => { /* dispatch by m.type */ },
})
```
Compose UI from `./components/ui`. Drone-natural prop shapes for
presence / message-feed / room-switcher / connection-banner are locked
into `__fixtures__/{drone_natural,realtime_patterns}.tsx`.

State pattern: useReducer keyed on `(prev, msg)` or per-variant
useState slots. Avoid one giant `useState<any[]>` log — drones write
quadratic re-renders that way.

## Reconnect
The bundled hook auto-reconnects every 2s on close. DO NOT remove that.
On reconnect, the server has no memory of who you were — clients must
re-send any identity (`{ type: "join", user, room }`) on `onopen`. Add
that to `useWebSocket` or in a wrapper hook.

If your goal needs offline-tolerant queueing, buffer outbound
messages while `connected === false` and flush them on the next open.

## Tests
- `useWebSocket connects → connected flag flips true`
- `Server-to-client message → onMessage callback fires with parsed JSON`
- `WS disconnect → connected flag flips false → auto-reconnect within 3s`
- `App-side dispatch on each message variant → correct UI surface
   (presence list updates / message appended / cursor moves)`

Use `vi.useFakeTimers()` + a mock WebSocket to drive these
deterministically. No live server needed for unit tests.

End-to-end with two clients (e.g. playwright with 2 pages) is the
gate the harness can run when proving the real deliverable.

## Build
shell_exec cd {project_path} && npm run build

## Deliver
message_result with one-line description.
