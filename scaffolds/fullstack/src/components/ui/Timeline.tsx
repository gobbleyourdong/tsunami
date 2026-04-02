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

/** Vertical timeline — for history, changelog, steps. */
export default function Timeline({ items }: TimelineProps) {
  return (
    <div style={{ position: "relative", paddingLeft: 32 }}>
      {/* Vertical line */}
      <div style={{ position: "absolute", left: 11, top: 8, bottom: 8, width: 2, background: "var(--border)" }} />
      {items.map((item, i) => (
        <div key={i} style={{ position: "relative", marginBottom: 24 }}>
          {/* Dot */}
          <div style={{
            position: "absolute", left: -27, top: 4, width: 14, height: 14,
            borderRadius: "50%", background: item.color || "var(--accent)",
            border: "2px solid var(--bg)",
          }} />
          {item.date && <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 2 }}>{item.date}</div>}
          <div style={{ fontWeight: 600, marginBottom: 2 }}>{item.title}</div>
          {item.description && <div style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5 }}>{item.description}</div>}
        </div>
      ))}
    </div>
  )
}
