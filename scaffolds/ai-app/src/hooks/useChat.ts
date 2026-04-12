import { useState, useCallback } from "react"

export interface Message {
  role: "user" | "assistant"
  content: string
}

/**
 * useChat — streaming SSE chat hook.
 * Sends messages to POST /api/chat, reads SSE deltas, appends tokens live.
 * Server must respond with: data: {"delta":"<token>"}\n\n  ...  data: [DONE]\n\n
 */
export function useChat(systemPrompt?: string) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendMessage = useCallback(async (content: string) => {
    setError(null)
    const userMsg: Message = { role: "user", content }
    const history = [...messages, userMsg]
    setMessages(history)
    setIsStreaming(true)

    // Append empty assistant bubble immediately
    setMessages([...history, { role: "assistant", content: "" }])

    try {
      const body: { messages: Message[]; systemPrompt?: string } = { messages: history }
      if (systemPrompt) body.systemPrompt = systemPrompt

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })

      if (!res.ok) throw new Error(`Server error ${res.status}`)

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value, { stream: true })
        for (const line of text.split("\n")) {
          if (!line.startsWith("data: ")) continue
          const data = line.slice(6).trim()
          if (data === "[DONE]") break
          try {
            const { delta } = JSON.parse(data) as { delta: string }
            if (delta) {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                updated[updated.length - 1] = { ...last, content: last.content + delta }
                return updated
              })
            }
          } catch { /* skip malformed chunk */ }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setIsStreaming(false)
    }
  }, [messages, systemPrompt])

  const clearMessages = useCallback(() => setMessages([]), [])

  return { messages, sendMessage, isStreaming, error, clearMessages }
}
