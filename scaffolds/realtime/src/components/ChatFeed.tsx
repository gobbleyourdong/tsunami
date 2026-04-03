import { useEffect, useRef } from "react"

interface Message {
  type: string
  text?: string
  username?: string
  timestamp?: number
}

interface ChatFeedProps {
  messages: Message[]
  currentUser?: string
}

export default function ChatFeed({ messages, currentUser }: ChatFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages.length])

  return (
    <div className="chat-feed">
      {messages.map((m, i) => {
        if (m.type === "presence") {
          return <div key={i} className="chat-system">{m.text || `${m.username} joined`}</div>
        }
        const isMe = m.username === currentUser
        return (
          <div key={i} className={`chat-bubble ${isMe ? "mine" : "theirs"}`}>
            {!isMe && <span className="chat-name">{m.username}</span>}
            <div className="chat-text">{m.text}</div>
            {m.timestamp && (
              <span className="chat-time">{new Date(m.timestamp).toLocaleTimeString()}</span>
            )}
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
