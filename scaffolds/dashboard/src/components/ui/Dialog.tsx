import { ReactNode, useEffect } from "react"

interface DialogProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
  children?: ReactNode
  actions?: ReactNode
}

export default function Dialog({ open, onClose, title, description, children, actions }: DialogProps) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open, onClose])

  useEffect(() => {
    if (open) document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = "" }
  }, [open])

  if (!open) return null

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(8, 9, 13, 0.8)',
        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
        animation: 'fade-in var(--duration-normal, 200ms) ease',
      }}
    >
      <div
        className="card"
        onClick={e => e.stopPropagation()}
        style={{
          maxWidth: 480, width: '100%', maxHeight: '85vh', overflow: 'auto',
          animation: 'scale-in var(--duration-slow, 400ms) cubic-bezier(0.22, 1.2, 0.36, 1)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            {title && <h2 style={{ fontSize: 'var(--text-lg, 1.25rem)', fontWeight: 700, marginBottom: 4, color: '#fff' }}>{title}</h2>}
            {description && <p style={{ color: 'var(--text-muted, #7a7f8e)', fontSize: 'var(--text-sm, 0.875rem)', marginBottom: 16, lineHeight: 1.6 }}>{description}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none', border: 'none', color: 'var(--text-dim, #4a4f5e)',
              fontSize: 20, cursor: 'pointer', padding: '2px 6px', lineHeight: 1,
              borderRadius: 6, transition: 'color 100ms',
            }}
          >
            ×
          </button>
        </div>
        {children}
        {actions && (
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border, rgba(255,255,255,0.06))' }}>
            {actions}
          </div>
        )}
      </div>
    </div>
  )
}
