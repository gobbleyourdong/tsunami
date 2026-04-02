import { ReactNode } from "react"

interface AlertProps {
  type?: "info" | "success" | "warning" | "error"
  title?: string
  children: ReactNode
}

const colors = {
  info: "var(--accent)",
  success: "#44cc44",
  warning: "#ffaa00",
  error: "#ff4444",
}

export default function Alert({ type = "info", title, children }: AlertProps) {
  const c = colors[type]
  return (
    <div style={{
      padding: "12px 16px", borderRadius: "var(--radius)",
      border: `1px solid ${c}44`, background: `${c}11`,
      borderLeft: `3px solid ${c}`,
    }}>
      {title && <div style={{ fontWeight: 600, marginBottom: 4, color: c }}>{title}</div>}
      <div style={{ fontSize: 14, color: "var(--text)" }}>{children}</div>
    </div>
  )
}
