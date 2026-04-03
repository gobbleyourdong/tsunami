import { useEffect, useRef } from "react"

interface Message {
  type: string
  text?: string
  username?: string
  timestamp?: number
  avatar?: string
}

interface ChatFeedProps {
  messages: Message[]
  currentUser?: string
  typingUsers?: string[]
}

export default function ChatFeed({ messages, currentUser, typingUsers = [] }: ChatFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages.length, typingUsers.length])

  return (
    <div className="chat-feed">
      {messages.map((m, i) => {
        if (m.type === "presence") {
          return (
            <div key={i} className="chat-system">
              {m.text || `${m.username} joined`}
            </div>
          )
        }
        const isMe = m.username === currentUser
        const showAvatar = !isMe && (i === 0 || messages[i - 1]?.username !== m.username)

        return (
          <div key={i} className={`chat-bubble ${isMe ? "mine" : "theirs"}`}>
            {!isMe && showAvatar && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <div className="avatar" style={{ width: 24, height: 24, fontSize: 10 }}>
                  {m.avatar
                    ? <img src={m.avatar} alt={m.username} />
                    : (m.username || '?').charAt(0).toUpperCase()
                  }
                </div>
                <span className="chat-name">{m.username}</span>
              </div>
            )}
            <div className="chat-text">{m.text}</div>
            {m.timestamp && (
              <span className="chat-time">
                {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        )
      })}

      {/* Typing indicator */}
      {typingUsers.length > 0 && (
        <div className="chat-system" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ display: 'flex', gap: 3 }}>
            <span className="typing-dot" style={{ animationDelay: '0ms' }} />
            <span className="typing-dot" style={{ animationDelay: '150ms' }} />
            <span className="typing-dot" style={{ animationDelay: '300ms' }} />
          </span>
          <span>
            {typingUsers.length === 1
              ? `${typingUsers[0]} is typing`
              : `${typingUsers.length} people typing`
            }
          </span>
          <style>{`
            .typing-dot {
              width: 6px; height: 6px; border-radius: 50%;
              background: var(--text-dim, #4a4f5e);
              animation: typing-bounce 1s ease-in-out infinite;
            }
            @keyframes typing-bounce {
              0%, 100% { transform: translateY(0); }
              50% { transform: translateY(-4px); }
            }
          `}</style>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
