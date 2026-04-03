import { useState, useCallback } from "react"

interface ToastMessage {
  id: number
  text: string
  type: "success" | "error" | "info" | "warning"
}

let toastId = 0
let addToastFn: ((text: string, type?: ToastMessage["type"]) => void) | null = null

/** Show a toast from anywhere: toast("Saved!") or toast("Error", "error") */
export function toast(text: string, type: ToastMessage["type"] = "info") {
  addToastFn?.(text, type)
}

/** Place <ToastContainer /> once in your App. Then call toast() from anywhere. */
export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  addToastFn = useCallback((text: string, type: ToastMessage["type"] = "info") => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, text, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }, [])

  const dismiss = (id: number) => setToasts(prev => prev.filter(t => t.id !== id))

  if (toasts.length === 0) return null

  const colors = {
    success: "var(--success)",
    error: "var(--danger)",
    warning: "var(--warning)",
    info: "var(--accent)",
  }
  const icons = { success: "✓", error: "✕", warning: "!", info: "i" }

  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 200,
      display: 'flex', flexDirection: 'column', gap: 8,
      pointerEvents: 'none',
    }}>
      {toasts.map(t => (
        <div
          key={t.id}
          className="toast"
          style={{
            position: 'relative',
            display: 'flex', alignItems: 'center', gap: 12,
            borderLeft: `3px solid ${colors[t.type]}`,
            pointerEvents: 'auto',
            cursor: 'pointer',
          }}
          onClick={() => dismiss(t.id)}
        >
          <span style={{
            width: 22, height: 22,
            borderRadius: '50%',
            background: colors[t.type],
            color: 'var(--bg-0)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, fontWeight: 700, flexShrink: 0,
          }}>
            {icons[t.type]}
          </span>
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  )
}
