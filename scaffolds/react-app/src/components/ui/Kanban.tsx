import { useState, ReactNode } from "react"

interface KanbanCard {
  id: string
  title: string
  description?: string
}

interface KanbanColumn {
  id: string
  title: string
  cards: KanbanCard[]
}

interface KanbanProps {
  columns: KanbanColumn[]
  onMove?: (cardId: string, fromCol: string, toCol: string) => void
}

/** Pre-built Kanban board — click cards to move to next column. */
export default function Kanban({ columns, onMove }: KanbanProps) {
  return (
    <div style={{ display: "flex", gap: 12, overflow: "auto", minHeight: 400 }}>
      {columns.map((col, ci) => (
        <div key={col.id} style={{
          flex: "1 0 250px", background: "var(--bg-card)", borderRadius: "var(--radius)",
          border: "1px solid var(--border)", padding: 12, display: "flex", flexDirection: "column",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>{col.title}</span>
            <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{col.cards.length}</span>
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
            {col.cards.map(card => (
              <div key={card.id}
                onClick={() => {
                  const nextCol = columns[ci + 1]
                  if (nextCol && onMove) onMove(card.id, col.id, nextCol.id)
                }}
                style={{
                  padding: 12, background: "var(--bg)", borderRadius: 6,
                  border: "1px solid var(--border)", cursor: ci < columns.length - 1 ? "pointer" : "default",
                  fontSize: 13,
                }}
              >
                <div style={{ fontWeight: 500 }}>{card.title}</div>
                {card.description && <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4 }}>{card.description}</div>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
