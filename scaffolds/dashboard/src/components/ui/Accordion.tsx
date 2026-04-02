import { useState, ReactNode } from "react"

interface AccordionItem {
  title: string
  content: ReactNode
}

interface AccordionProps {
  items: AccordionItem[]
  multiple?: boolean
}

export default function Accordion({ items, multiple = false }: AccordionProps) {
  const [open, setOpen] = useState<Set<number>>(new Set())

  const toggle = (i: number) => {
    setOpen(prev => {
      const next = new Set(multiple ? prev : [])
      if (prev.has(i)) next.delete(i); else next.add(i)
      return next
    })
  }

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
      {items.map((item, i) => (
        <div key={i}>
          <button onClick={() => toggle(i)} style={{
            width: "100%", textAlign: "left", padding: "12px 16px",
            background: open.has(i) ? "var(--bg-hover)" : "var(--bg-card)",
            border: "none", borderBottom: "1px solid var(--border)",
            color: "var(--text)", cursor: "pointer", fontSize: 14, fontWeight: 500,
            display: "flex", justifyContent: "space-between",
          }}>
            {item.title}
            <span style={{ transform: open.has(i) ? "rotate(180deg)" : "none", transition: "0.2s" }}>▼</span>
          </button>
          {open.has(i) && <div style={{ padding: 16, borderBottom: "1px solid var(--border)", fontSize: 14, color: "var(--text-muted)" }}>{item.content}</div>}
        </div>
      ))}
    </div>
  )
}
