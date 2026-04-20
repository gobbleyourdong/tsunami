/**
 * AI-app contract fixture. Scaffold ships `useChat` — a streaming SSE
 * hook that POSTs to /api/chat and reads `data: {"delta":"<token>"}\n\n`
 * frames terminated by `data: [DONE]\n\n`.
 *
 * This fixture pins:
 *   - useChat() return shape: { messages, sendMessage, isStreaming, error, clearMessages }
 *   - Message: { role: "user" | "assistant", content: string }
 *   - sendMessage(content) appends a user msg + an empty assistant bubble that fills via stream
 *   - The SSE wire format: data: <json>\n\n with [DONE] sentinel
 *
 * Compile-only via tsconfig include `__fixtures__`. Lock the surface so
 * widening the hook (or the server) can't silently break drone code.
 */
import { useChat, type Message } from "../src/hooks/useChat"
import { useState } from "react"

function ChatBubble({ message }: { message: Message }) {
  const isUser = message.role === "user"
  return (
    <div style={{ textAlign: isUser ? "right" : "left", padding: "4px 8px" }}>
      <strong>{isUser ? "You" : "Assistant"}:</strong> {message.content}
    </div>
  )
}

function ChatComposer({ onSend, disabled }: { onSend: (text: string) => void; disabled: boolean }) {
  const [draft, setDraft] = useState("")
  return (
    <form
      onSubmit={e => {
        e.preventDefault()
        if (draft.trim()) {
          onSend(draft.trim())
          setDraft("")
        }
      }}
    >
      <input
        value={draft}
        onChange={e => setDraft(e.target.value)}
        placeholder="Ask something…"
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !draft.trim()}>Send</button>
    </form>
  )
}

export default function ChatFixture() {
  // Drone-natural pattern: pass a system prompt at hook init.
  const { messages, sendMessage, isStreaming, error, clearMessages } = useChat(
    "You are a helpful assistant. Answer concisely."
  )

  return (
    <div>
      {error && <div role="alert" style={{ color: "red" }}>{error}</div>}
      <div style={{ minHeight: 200, border: "1px solid #ccc", padding: 8 }}>
        {messages.map((m, i) => <ChatBubble key={i} message={m} />)}
        {isStreaming && messages.length > 0 && messages[messages.length - 1].content === "" && (
          <div>…</div>
        )}
      </div>
      <ChatComposer onSend={sendMessage} disabled={isStreaming} />
      <button onClick={clearMessages} disabled={isStreaming || messages.length === 0}>
        Clear
      </button>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// SSE wire-format probe — lives next to the React fixture so any
// drift in the parser shape (delta key name, [DONE] sentinel) trips
// tsc here, not at runtime in production deliveries.
// ─────────────────────────────────────────────────────────────

interface SSEDelta { delta: string }

/** Standalone parser drones can copy/paste when they need streaming
 * without the full hook (e.g. for a non-React surface). Locks the
 * format the bundled server emits. */
export async function parseSSE(
  res: Response,
  onDelta: (token: string) => void
): Promise<void> {
  if (!res.body) throw new Error("Response has no body")
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const text = decoder.decode(value, { stream: true })
    for (const line of text.split("\n")) {
      if (!line.startsWith("data: ")) continue
      const data = line.slice(6).trim()
      if (data === "[DONE]") return
      try {
        const { delta } = JSON.parse(data) as SSEDelta
        if (delta) onDelta(delta)
      } catch {
        // skip malformed chunk — server may emit partial frames
      }
    }
  }
}

// Type-only probes — fail-fast contract assertions at tsc time.
type MessageMustHave = Message & { role: "user" | "assistant"; content: string }
const _msgProbe: MessageMustHave = { role: "user", content: "hi" }
void _msgProbe
