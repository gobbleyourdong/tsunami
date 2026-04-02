import { ReactNode } from "react"

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
}

/** Simple modal dialog. Use open/onClose to control visibility. */
export default function Modal({ open, onClose, title, children }: ModalProps) {
  if (!open) return null

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 50,
        background: "rgba(0,0,0,0.7)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{ maxWidth: 500, width: "90%", maxHeight: "80vh", overflow: "auto" }}
        onClick={e => e.stopPropagation()}
      >
        {title && <h2 style={{ marginBottom: 16 }}>{title}</h2>}
        {children}
      </div>
    </div>
  )
}
