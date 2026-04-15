import { useState, useEffect, useCallback } from "react"

interface Notification {
  id: string
  title: string
  message?: string
  type?: "info" | "success" | "warning" | "error"
  duration?: number
  action?: { label: string; onClick: () => void }
  persistent?: boolean
  timestamp?: number
}

interface NotificationCenterProps {
  notifications: Notification[]
  onDismiss: (id: string) => void
  position?: "top-right" | "top-left" | "bottom-right" | "bottom-left"
  maxVisible?: number
}

const TYPE_COLORS = {
  info: "var(--accent, #4a9eff)",
  success: "#10b981",
  warning: "#f59e0b",
  error: "#ef4444",
}

function Toast({ notification, onDismiss }: { notification: Notification; onDismiss: () => void }) {
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    if (notification.persistent) return
    const ms = notification.duration || 5000
    const timer = setTimeout(() => { setExiting(true); setTimeout(onDismiss, 200) }, ms)
    return () => clearTimeout(timer)
  }, [notification, onDismiss])

  const color = TYPE_COLORS[notification.type || "info"]

  return (
    <div style={{
      background: "var(--bg-secondary, #111827)",
      border: "1px solid var(--border, rgba(255,255,255,0.08))",
      borderLeft: `3px solid ${color}`,
      borderRadius: "var(--radius-md, 8px)",
      padding: "12px 16px",
      maxWidth: 360, width: "100%",
      boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
      opacity: exiting ? 0 : 1,
      transform: exiting ? "translateX(20px)" : "translateX(0)",
      transition: "opacity 200ms, transform 200ms",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary, #e2e8f0)" }}>
            {notification.title}
          </div>
          {notification.message && (
            <div style={{ fontSize: 13, color: "var(--text-secondary, #94a3b8)", marginTop: 4, lineHeight: 1.4 }}>
              {notification.message}
            </div>
          )}
          {notification.action && (
            <button
              onClick={notification.action.onClick}
              style={{
                marginTop: 8, padding: "4px 10px", fontSize: 12,
                background: color, color: "#fff", border: "none",
                borderRadius: 4, cursor: "pointer",
              }}
            >
              {notification.action.label}
            </button>
          )}
        </div>
        <button
          onClick={() => { setExiting(true); setTimeout(onDismiss, 200) }}
          style={{
            background: "none", border: "none", color: "var(--text-dim, #4a4f5e)",
            cursor: "pointer", fontSize: 16, padding: "0 4px", lineHeight: 1,
          }}
        >
          x
        </button>
      </div>
    </div>
  )
}

const POSITION_STYLES = {
  "top-right": { top: 16, right: 16 },
  "top-left": { top: 16, left: 16 },
  "bottom-right": { bottom: 16, right: 16 },
  "bottom-left": { bottom: 16, left: 16 },
} as const

export function NotificationCenter({ notifications, onDismiss, position = "top-right", maxVisible = 5 }: NotificationCenterProps) {
  const visible = notifications.slice(-maxVisible)
  const pos = POSITION_STYLES[position]

  return (
    <div style={{
      position: "fixed", ...pos, zIndex: 300,
      display: "flex", flexDirection: position.startsWith("bottom") ? "column-reverse" : "column",
      gap: 8, pointerEvents: "none",
    }}>
      {visible.map(n => (
        <div key={n.id} style={{ pointerEvents: "auto" }}>
          <Toast notification={n} onDismiss={() => onDismiss(n.id)} />
        </div>
      ))}
    </div>
  )
}

export default NotificationCenter
