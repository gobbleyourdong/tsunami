import { useNotes, type Note } from "../lib/notes-store"

type Props = { onSelect: (id: string) => void }

export default function NoteList({ onSelect }: Props) {
  const notes = useNotes()
  if (notes.length === 0) {
    return <div className="empty">No notes yet. Tap + to create one.</div>
  }
  return (
    <div className="notes-list">
      {notes.map((n: Note) => (
        <div key={n.id} className="note-row" onClick={() => onSelect(n.id)}>
          <h3>{n.title || "Untitled"}</h3>
          <div className="body-preview">{firstLine(n.body) || "No body"}</div>
          <div className="meta">{new Date(n.updated_at).toLocaleString()}</div>
        </div>
      ))}
    </div>
  )
}

function firstLine(body: string): string {
  const idx = body.indexOf("\n")
  return idx === -1 ? body : body.slice(0, idx)
}
