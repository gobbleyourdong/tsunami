# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Server](#server)
- [ ] [Client](#client)
- [ ] [Wire format](#wire-format)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
React (Vite) client + Express server that proxies to an OpenAI-compatible
streaming endpoint. Bundled:
- `server/index.js` — `POST /api/chat` accepts
  `{ messages: [{role, content}], systemPrompt? }`, returns SSE stream.
- `src/hooks/useChat.ts` — `useChat(systemPrompt?)` returning
  `{ messages, sendMessage, isStreaming, error, clearMessages }`.
- Streaming tokens appended live to the last assistant bubble.

Pin: SSE format (NOT JSON-over-fetch, NOT WebSocket). Endpoint URL via
`VITE_MODEL_ENDPOINT` env (or hardcoded default). The contract is
locked in `__fixtures__/chat_stream.tsx` — copy `parseSSE` from
there if you need a non-React surface.

## Server
Customize `server/index.js`:
- Forward request to the upstream (OpenAI / Together / Groq / Tsunami's
  own :8090 — any OpenAI-compatible endpoint).
- Stream upstream response chunks to the client as `data: <json>\n\n`.
- Send `data: [DONE]\n\n` and `res.end()` when upstream completes.
- On upstream error, send `data: {"error":"<msg>"}\n\n` then `[DONE]`.

Required headers:
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```
Without `text/event-stream` some proxies buffer the response and the
stream looks broken from the client.

## Client
Use the bundled hook:
```tsx
const { messages, sendMessage, isStreaming, error, clearMessages } =
  useChat("You are a helpful assistant.")

await sendMessage("Hello")
// messages now: [{role:"user",content:"Hello"}, {role:"assistant",content:"...streaming..."}]
```
Render `messages` as a list. Show a spinner / typing indicator when
`isStreaming === true` and the last assistant bubble is empty. Disable
the composer while streaming (drones forget this and end up with two
overlapping streams).

## Wire format
The bundled server emits and the bundled hook expects:
```
data: {"delta":"H"}\n\n
data: {"delta":"e"}\n\n
data: {"delta":"llo"}\n\n
data: [DONE]\n\n
```
- Each line starts with `data: ` (six chars including space).
- JSON payload has `{ "delta": "<token>" }`. Other keys are ignored.
- `[DONE]` (no JSON) terminates the stream.
- Malformed chunks are dropped — the hook doesn't crash.

Don't change this format without also updating `useChat` and any
drone code that copy-pasted the parser. Add new fields by extending
the JSON object (`{ "delta": "...", "tokens_used": 42 }`) — additive
changes don't break existing parsers.

## Tests
- `sendMessage appends user msg + empty assistant bubble immediately`
- `Stream chunks accumulate into the assistant content`
- `[DONE] sentinel ends streaming → isStreaming flips false`
- `Server error → error state populated, isStreaming false`
- `Malformed chunk → hook does not crash, skips the chunk`
- `clearMessages → messages = []`

Mock fetch with a ReadableStream body that yields fixture chunks.
The bundled hook reads via `res.body.getReader()` — give it a
synthetic stream and assert the resulting messages array.

## Build
shell_exec cd {project_path} && npm run build
(runs tsc --noEmit + vite build; tsc also checks `__fixtures__/`)

Dev workflow: `npm run dev` runs vite + `node --watch server/index.js`
concurrently. Set `MODEL_ENDPOINT` (server) and `VITE_MODEL_ENDPOINT`
(client) in `.env` if you point at a non-default upstream.

## Deliver
message_result with one-line description.
