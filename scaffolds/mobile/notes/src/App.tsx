import { useState } from "react"
import { NoteList, NoteEditor } from "./components"
import { newNote } from "./lib/notes-store"

export default function App() {
  const [editingId, setEditingId] = useState<string | null>(null)

  function onNew() {
    const note = newNote()
    setEditingId(note.id)
  }

  if (editingId) {
    return (
      <div className="notes">
        <NoteEditor id={editingId} onBack={() => setEditingId(null)} />
      </div>
    )
  }

  return (
    <div className="notes">
      <header className="notes-header">
        <h1>Notes</h1>
        <button className="header-new" onClick={onNew}>+ New</button>
      </header>
      <NoteList onSelect={setEditingId} />
    </div>
  )
}
