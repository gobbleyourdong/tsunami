import { ReactNode, useRef, useState } from "react"

interface GlowCardProps {
  children: ReactNode
  color?: string
  glowColor?: string  // alias drones reach for
  intensity?: number  // 0..1 — opacity multiplier on the glow
  padding?: "none" | "sm" | "md" | "lg" | "xl" | number
  style?: React.CSSProperties
  className?: string
}

const PAD: Record<string, number> = { none: 0, sm: 12, md: 18, lg: 24, xl: 32 }

/** Card with a glow effect that follows the mouse cursor. */
export function GlowCard({
  children,
  color,
  glowColor,
  intensity = 1,
  padding = "lg",
  style,
  className,
}: GlowCardProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const [hover, setHover] = useState(false)

  const glow = glowColor ?? color ?? "var(--accent, #4a9eff)"
  const pad = typeof padding === "number" ? padding : PAD[padding] ?? 24
  const opacityHex = Math.max(0, Math.min(1, intensity))
    .toString(16)
    .replace(/^0\./, "")
    .slice(0, 2)
    .padEnd(2, "0")

  const handleMove = (e: React.MouseEvent) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    setPos({ x: e.clientX - rect.left, y: e.clientY - rect.top })
  }

  return (
    <div
      ref={ref}
      className={className}
      onMouseMove={handleMove}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        position: 'relative',
        overflow: 'hidden',
        background: 'var(--bg-1, #111318)',
        border: `1px solid ${hover ? 'var(--border-hover, rgba(255,255,255,0.12))' : 'var(--border, rgba(255,255,255,0.06))'}`,
        borderRadius: 'var(--radius-lg, 16px)',
        padding: pad,
        transition: 'border-color 200ms, box-shadow 300ms',
        boxShadow: hover ? '0 4px 20px rgba(0,0,0,0.3)' : 'none',
        ...style,
      }}
    >
      {hover && (
        <div style={{
          position: 'absolute',
          pointerEvents: 'none',
          width: 250,
          height: 250,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${glow}${opacityHex} 0%, transparent 70%)`,
          left: pos.x - 125,
          top: pos.y - 125,
          transition: 'left 50ms, top 50ms',
        }} />
      )}
      <div style={{ position: 'relative', zIndex: 1 }}>{children}</div>
    </div>
  )
}

export default GlowCard
