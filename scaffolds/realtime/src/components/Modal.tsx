import { ReactNode, useEffect } from "react"

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
  size?: "sm" | "md" | "lg"
}

export default function Modal({ open, onClose, title, children, size = "md" }: ModalProps) {
  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open, onClose])

  // Prevent body scroll when open
  useEffect(() => {
    if (open) document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = "" }
  }, [open])

  if (!open) return null

  const widths = { sm: 400, md: 540, lg: 720 }

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(8, 9, 13, 0.8)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'fade-in var(--duration-normal) ease',
        padding: 20,
      }}
    >
      <div
        className="card"
        onClick={e => e.stopPropagation()}
        style={{
          maxWidth: widths[size],
          width: '100%',
          maxHeight: '85vh',
          overflow: 'auto',
          animation: 'scale-in var(--duration-slow) var(--ease-spring)',
        }}
      >
        {title && (
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginBottom: 20, paddingBottom: 16,
            borderBottom: '1px solid var(--border)',
          }}>
            <h2 style={{ fontSize: 'var(--text-lg)', margin: 0 }}>{title}</h2>
            <button
              onClick={onClose}
              className="ghost"
              style={{ padding: '4px 8px', fontSize: 18, lineHeight: 1 }}
              aria-label="Close"
            >
              ×
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  )
}
