import { useEffect, useRef, useState } from "react"
import { findNote, updateNote, deleteNote } from "../lib/notes-store"

type Props = { id: string; onBack: () => void }

export default function NoteEditor({ id, onBack }: Props) {
  const note = findNote(id)
  const [title, setTitle] = useState(note?.title ?? "")
  const [body, setBody] = useState(note?.body ?? "")
  const saveTimer = useRef<number | null>(null)

  useEffect(() => {
    if (!note) return
    if (saveTimer.current != null) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => {
      updateNote(id, { title, body })
    }, 350)
    return () => {
      if (saveTimer.current != null) window.clearTimeout(saveTimer.current)
    }
  }, [id, title, body, note])

  if (!note) return <div className="empty">Note not found.</div>

  function onDelete() {
    if (!confirm("Delete this note?")) return
    deleteNote(id)
    onBack()
  }

  return (
    <div className="editor">
      <button className="back" onClick={onBack}>← Notes</button>
      <input
        className="title"
        placeholder="Title"
        value={title}
        onChange={e => setTitle(e.target.value)}
      />
      <textarea
        placeholder="Write something…"
        value={body}
        onChange={e => setBody(e.target.value)}
      />
      <div className="actions">
        <button className="danger" onClick={onDelete}>Delete</button>
        <button className="primary" onClick={onBack}>Done</button>
      </div>
    </div>
  )
}
