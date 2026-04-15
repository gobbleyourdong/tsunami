import { ReactNode } from "react"

interface TimelineItem {
  title: string
  description?: string
  date?: string
  icon?: ReactNode
  color?: string
}

interface TimelineProps {
  items: TimelineItem[]
}

export function Timeline({ items }: TimelineProps) {
  return (
    <div style={{ position: 'relative', paddingLeft: 36 }}>
      {/* Vertical line */}
      <div style={{
        position: 'absolute', left: 11, top: 8, bottom: 8,
        width: 2, background: 'var(--border, rgba(255,255,255,0.06))',
      }} />
      {items.map((item, i) => (
        <div key={i} style={{ position: 'relative', marginBottom: 28 }}>
          {/* Dot */}
          <div style={{
            position: 'absolute', left: -31, top: 4,
            width: 14, height: 14, borderRadius: '50%',
            background: item.color || 'var(--accent, #4a9eff)',
            border: '3px solid var(--bg-0, #08090d)',
            boxShadow: `0 0 6px ${item.color || 'rgba(74,158,255,0.3)'}`,
          }} />
          {item.date && (
            <div style={{
              fontSize: 'var(--text-xs, 0.75rem)',
              color: 'var(--text-dim, #4a4f5e)',
              marginBottom: 3,
              fontWeight: 500,
            }}>
              {item.date}
            </div>
          )}
          <div style={{ fontWeight: 700, color: '#fff', fontSize: 'var(--text-sm, 0.875rem)', marginBottom: 3 }}>
            {item.title}
          </div>
          {item.description && (
            <div style={{
              fontSize: 'var(--text-sm, 0.875rem)',
              color: 'var(--text-muted, #7a7f8e)',
              lineHeight: 1.6,
            }}>
              {item.description}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default Timeline
