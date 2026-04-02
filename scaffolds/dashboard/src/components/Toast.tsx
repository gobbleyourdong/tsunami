import { useState, useEffect, useCallback } from "react"

interface ToastMessage {
  id: number
  text: string
  type: "success" | "error" | "info"
}

let toastId = 0
let addToastFn: ((text: string, type?: "success" | "error" | "info") => void) | null = null

/** Show a toast from anywhere: toast("Saved!") or toast("Error", "error") */
export function toast(text: string, type: "success" | "error" | "info" = "info") {
  addToastFn?.(text, type)
}

/** Place <ToastContainer /> once in your App. Then call toast() from anywhere. */
export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  addToastFn = useCallback((text: string, type: "success" | "error" | "info" = "info") => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, text, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3000)
  }, [])

  if (toasts.length === 0) return null

  const colors = { success: "#4f4", error: "#f44", info: "var(--accent)" }

  return (
    <div style={{ position: "fixed", bottom: 20, right: 20, zIndex: 100, display: "flex", flexDirection: "column", gap: 8 }}>
      {toasts.map(t => (
        <div key={t.id} className="card" style={{ borderLeft: `3px solid ${colors[t.type]}`, minWidth: 250 }}>
          {t.text}
        </div>
      ))}
    </div>
  )
}
