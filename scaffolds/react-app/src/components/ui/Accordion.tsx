import { useState, ReactNode } from "react"

interface AccordionItem {
  title: string
  content: ReactNode
}

interface AccordionProps {
  items: AccordionItem[]
  multiple?: boolean
}

export function Accordion({ items, multiple = false }: AccordionProps) {
  const [open, setOpen] = useState<Set<number>>(new Set())

  const toggle = (i: number) => {
    setOpen(prev => {
      const next = new Set(multiple ? prev : [])
      if (prev.has(i)) next.delete(i); else next.add(i)
      return next
    })
  }

  return (
    <div style={{
      border: '1px solid var(--border, rgba(255,255,255,0.06))',
      borderRadius: 'var(--radius, 10px)',
      overflow: 'hidden',
    }}>
      {items.map((item, i) => {
        const isOpen = open.has(i)
        return (
          <div key={i}>
            <button
              onClick={() => toggle(i)}
              style={{
                width: '100%', textAlign: 'left',
                padding: '14px 18px',
                background: isOpen ? 'var(--bg-2, #191c24)' : 'var(--bg-1, #111318)',
                border: 'none',
                borderBottom: '1px solid var(--border, rgba(255,255,255,0.06))',
                color: isOpen ? '#fff' : 'var(--text, #e2e4e9)',
                cursor: 'pointer',
                fontSize: 'var(--text-sm, 0.875rem)',
                fontWeight: 600,
                fontFamily: 'inherit',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                transition: 'background 150ms',
              }}
            >
              {item.title}
              <span style={{
                transform: isOpen ? 'rotate(180deg)' : 'none',
                transition: 'transform 200ms cubic-bezier(0.16, 1, 0.3, 1)',
                fontSize: 12,
                color: 'var(--text-dim, #4a4f5e)',
              }}>
                ▼
              </span>
            </button>
            {isOpen && (
              <div style={{
                padding: '16px 18px',
                borderBottom: '1px solid var(--border, rgba(255,255,255,0.06))',
                fontSize: 'var(--text-sm, 0.875rem)',
                color: 'var(--text-muted, #7a7f8e)',
                lineHeight: 1.7,
                background: 'var(--bg-1, #111318)',
              }}>
                {item.content}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default Accordion
