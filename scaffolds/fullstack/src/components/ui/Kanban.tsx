interface KanbanCard {
  id: string
  title: string
  description?: string
  tag?: string
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

export default function Kanban({ columns, onMove }: KanbanProps) {
  return (
    <div style={{ display: 'flex', gap: 14, overflow: 'auto', minHeight: 400, padding: '2px 0' }}>
      {columns.map((col, ci) => (
        <div key={col.id} style={{
          flex: '1 0 260px',
          background: 'var(--bg-1, #111318)',
          borderRadius: 'var(--radius-lg, 16px)',
          border: '1px solid var(--border, rgba(255,255,255,0.06))',
          padding: 14,
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginBottom: 14, paddingBottom: 10,
            borderBottom: '1px solid var(--border, rgba(255,255,255,0.06))',
          }}>
            <span style={{ fontWeight: 700, fontSize: 'var(--text-sm, 0.875rem)', color: '#fff' }}>
              {col.title}
            </span>
            <span style={{
              fontSize: 'var(--text-xs, 0.75rem)',
              fontWeight: 600,
              color: 'var(--text-dim, #4a4f5e)',
              background: 'var(--bg-2, #191c24)',
              padding: '2px 8px',
              borderRadius: 100,
            }}>
              {col.cards.length}
            </span>
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {col.cards.map(card => (
              <div
                key={card.id}
                onClick={() => {
                  const nextCol = columns[ci + 1]
                  if (nextCol && onMove) onMove(card.id, col.id, nextCol.id)
                }}
                style={{
                  padding: 14,
                  background: 'var(--bg-2, #191c24)',
                  borderRadius: 'var(--radius, 10px)',
                  border: '1px solid var(--border, rgba(255,255,255,0.06))',
                  cursor: ci < columns.length - 1 ? 'pointer' : 'default',
                  transition: 'all 150ms cubic-bezier(0.16, 1, 0.3, 1)',
                }}
                onMouseEnter={e => {
                  if (ci < columns.length - 1) {
                    e.currentTarget.style.borderColor = 'var(--border-hover, rgba(255,255,255,0.12))'
                    e.currentTarget.style.transform = 'translateY(-1px)'
                  }
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border, rgba(255,255,255,0.06))'
                  e.currentTarget.style.transform = 'none'
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 'var(--text-sm, 0.875rem)', color: 'var(--text, #e2e4e9)' }}>
                  {card.title}
                </div>
                {card.description && (
                  <div style={{
                    color: 'var(--text-muted, #7a7f8e)',
                    fontSize: 'var(--text-xs, 0.75rem)',
                    marginTop: 6,
                    lineHeight: 1.5,
                  }}>
                    {card.description}
                  </div>
                )}
                {card.tag && (
                  <span style={{
                    display: 'inline-block', marginTop: 8,
                    padding: '2px 8px',
                    fontSize: 'var(--text-xs, 0.75rem)',
                    fontWeight: 600,
                    borderRadius: 100,
                    background: 'rgba(74, 158, 255, 0.12)',
                    color: 'var(--accent, #4a9eff)',
                  }}>
                    {card.tag}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
