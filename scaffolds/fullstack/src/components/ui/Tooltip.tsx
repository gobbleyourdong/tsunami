import { useState, ReactNode } from "react"

interface TooltipProps {
  text: string
  children: ReactNode
  position?: "top" | "bottom"
}

export default function Tooltip({ text, children, position = "top" }: TooltipProps) {
  const [show, setShow] = useState(false)
  const pos = position === "top"
    ? { bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)" }
    : { top: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)" }

  return (
    <div style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <div style={{
          position: "absolute", ...pos,
          background: "var(--bg-card)", border: "1px solid var(--border)",
          borderRadius: 6, padding: "6px 10px", fontSize: 12,
          color: "var(--text)", whiteSpace: "nowrap", zIndex: 50,
          boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
        }}>
          {text}
        </div>
      )}
    </div>
  )
}
