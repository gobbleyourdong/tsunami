import { useState } from "react"

interface ChatInputProps {
  onSend: (text: string) => void
  placeholder?: string
  disabled?: boolean
}

export default function ChatInput({ onSend, placeholder = "Type a message...", disabled }: ChatInputProps) {
  const [text, setText] = useState("")

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText("")
  }

  return (
    <div className="chat-input-bar">
      <input
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => e.key === "Enter" && handleSend()}
        placeholder={placeholder}
        disabled={disabled}
      />
      <button onClick={handleSend} disabled={disabled || !text.trim()} className="primary">
        Send
      </button>
    </div>
  )
}
