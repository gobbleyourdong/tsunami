import { useState, type FormEvent } from "react"
import { sendMessage } from "../lib/chat-store"

export default function Composer() {
  const [text, setText] = useState("")

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    sendMessage(text)
    setText("")
  }

  return (
    <form className="chat-input" onSubmit={onSubmit}>
      <input
        type="text"
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Message…"
        autoComplete="off"
      />
      <button type="submit" disabled={!text.trim()}>Send</button>
    </form>
  )
}
