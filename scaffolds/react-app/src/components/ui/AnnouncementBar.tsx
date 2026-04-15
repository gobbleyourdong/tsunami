import { useState, useEffect } from "react"

interface AnnouncementBarProps {
  text: string
  link?: { text: string; href: string }
  countdownTo?: string  // ISO date for countdown
  dismissable?: boolean
  variant?: "default" | "urgent" | "promo"
}

/** Sticky announcement bar with optional countdown + dismiss. */
export function AnnouncementBar({ text, link, countdownTo, dismissable = true, variant = "default" }: AnnouncementBarProps) {
  const [dismissed, setDismissed] = useState(false)
  const [countdown, setCountdown] = useState("")

  useEffect(() => {
    if (!countdownTo) return
    const target = new Date(countdownTo).getTime()
    const tick = () => {
      const diff = target - Date.now()
      if (diff <= 0) { setCountdown("Expired"); return }
      const h = Math.floor(diff / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setCountdown(`${h}h ${String(m).padStart(2,"0")}m ${String(s).padStart(2,"0")}s`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [countdownTo])

  if (dismissed) return null

  const colors = { default: "var(--accent)", urgent: "#dc2626", promo: "#6366f1" }
  const bg = colors[variant]

  return (
    <div style={{ width: "100%", background: bg, color: "#fff", fontSize: 13, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "8px 16px", position: "relative", zIndex: 60 }}>
      <span>{text}</span>
      {countdown && <span style={{ fontWeight: 700, background: "rgba(255,255,255,0.2)", padding: "2px 8px", borderRadius: 4, fontSize: 12, fontVariantNumeric: "tabular-nums" }}>{countdown}</span>}
      {link && <a href={link.href} style={{ color: "#fff", fontWeight: 700, textDecoration: "underline" }}>{link.text}</a>}
      {dismissable && <button onClick={() => setDismissed(true)} style={{ position: "absolute", right: 12, background: "none", border: "none", color: "#fff", cursor: "pointer", opacity: 0.6, fontSize: 16 }}>×</button>}
    </div>
  )
}

export default AnnouncementBar
