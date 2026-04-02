import { ReactNode, useRef, useState } from "react"

interface GlowCardProps {
  children: ReactNode
  color?: string
  style?: React.CSSProperties
}

/** Card with a glow effect that follows the mouse. */
export default function GlowCard({ children, color = "var(--accent)", style }: GlowCardProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const [hover, setHover] = useState(false)

  const handleMove = (e: React.MouseEvent) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    setPos({ x: e.clientX - rect.left, y: e.clientY - rect.top })
  }

  return (
    <div
      ref={ref}
      onMouseMove={handleMove}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        position: "relative", overflow: "hidden",
        background: "var(--bg-card)", border: "1px solid var(--border)",
        borderRadius: 12, padding: 24, ...style,
      }}
    >
      {hover && (
        <div style={{
          position: "absolute", pointerEvents: "none",
          width: 200, height: 200, borderRadius: "50%",
          background: `radial-gradient(circle, ${color}22 0%, transparent 70%)`,
          left: pos.x - 100, top: pos.y - 100,
        }} />
      )}
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  )
}
