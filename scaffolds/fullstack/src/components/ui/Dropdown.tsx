import { useState, useRef, useEffect, ReactNode } from "react"

interface DropdownItem {
  label: string
  onClick: () => void
  icon?: string
  danger?: boolean
  divider?: boolean
}

interface DropdownProps {
  trigger: ReactNode
  items: DropdownItem[]
  align?: "left" | "right"
}

export default function Dropdown({ trigger, items, align = "right" }: DropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <div onClick={() => setOpen(!open)} style={{ cursor: 'pointer' }}>{trigger}</div>
      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 6px)',
          [align === 'right' ? 'right' : 'left']: 0,
          minWidth: 180,
          background: 'var(--bg-2, #191c24)',
          border: '1px solid var(--border-hover, rgba(255,255,255,0.12))',
          borderRadius: 'var(--radius, 10px)',
          padding: '6px',
          zIndex: 100,
          boxShadow: '0 12px 40px rgba(0,0,0,0.5), 0 4px 12px rgba(0,0,0,0.3)',
          animation: 'scale-in 200ms cubic-bezier(0.22, 1.2, 0.36, 1)',
        }}>
          {items.map((item, i) =>
            item.divider ? (
              <div key={i} style={{ height: 1, background: 'var(--border, rgba(255,255,255,0.06))', margin: '4px 0' }} />
            ) : (
              <button
                key={i}
                onClick={() => { item.onClick(); setOpen(false) }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  width: '100%', textAlign: 'left',
                  background: 'none', border: 'none',
                  color: item.danger ? 'var(--danger, #f06060)' : 'var(--text, #e2e4e9)',
                  padding: '9px 12px', cursor: 'pointer',
                  fontSize: 'var(--text-sm, 0.875rem)',
                  fontWeight: 500,
                  borderRadius: 6,
                  transition: 'background 100ms',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-3, #21252f)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'none')}
              >
                {item.icon && <span style={{ fontSize: 16, opacity: 0.6 }}>{item.icon}</span>}
                {item.label}
              </button>
            )
          )}
        </div>
      )}
    </div>
  )
}
