import { ReactNode } from "react"

// TimelineItem is a permissive shape — drones write {year, event} for
// history timelines, {date, title, body} for change logs, {label} for
// minimal variants. All of these should Just Work. Any string field
// renders; the component picks in order title → event → label for the
// main line and date → year for the date line.
interface TimelineItem {
  title?: string
  event?: string
  label?: string
  description?: string
  body?: string
  date?: string
  year?: string | number
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
          {(item.date ?? item.year) && (
            <div style={{
              fontSize: 'var(--text-xs, 0.75rem)',
              color: 'var(--text-dim, #4a4f5e)',
              marginBottom: 3,
              fontWeight: 500,
            }}>
              {item.date ?? item.year}
            </div>
          )}
          <div style={{ fontWeight: 700, color: '#fff', fontSize: 'var(--text-sm, 0.875rem)', marginBottom: 3 }}>
            {item.title ?? item.event ?? item.label ?? ""}
          </div>
          {(item.description ?? item.body) && (
            <div style={{
              fontSize: 'var(--text-sm, 0.875rem)',
              color: 'var(--text-muted, #7a7f8e)',
              lineHeight: 1.6,
            }}>
              {item.description ?? item.body}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default Timeline
