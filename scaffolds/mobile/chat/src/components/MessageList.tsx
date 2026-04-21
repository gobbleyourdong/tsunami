import { useEffect, useRef } from "react"
import { useMessages, type Message } from "../lib/chat-store"

export default function MessageList() {
  const messages = useMessages()
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages.length])

  return (
    <div className="chat-body">
      {messages.map((m: Message) => (
        <div key={m.id} className={`msg ${m.sender === "me" ? "me" : "them"}`}>
          <div>{m.body}</div>
          <div className="msg-meta">
            {new Date(m.sent_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  )
}
