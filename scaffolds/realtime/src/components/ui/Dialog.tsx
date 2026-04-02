import { ReactNode } from "react"

interface DialogProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
  children?: ReactNode
  actions?: ReactNode
}

export default function Dialog({ open, onClose, title, description, children, actions }: DialogProps) {
  if (!open) return null
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, padding: 24, maxWidth: 480, width: "90%", maxHeight: "80vh", overflow: "auto" }} onClick={e => e.stopPropagation()}>
        {title && <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 4 }}>{title}</h2>}
        {description && <p style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 16 }}>{description}</p>}
        {children}
        {actions && <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>{actions}</div>}
      </div>
    </div>
  )
}
