import { ReactNode, useRef, useState } from "react"

interface GlowCardProps {
  children: ReactNode
  color?: string
  style?: React.CSSProperties
  className?: string
}

/** Card with a glow effect that follows the mouse cursor. */
export default function GlowCard({ children, color = "var(--accent, #34d4b0)", style, className }: GlowCardProps) {
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
        padding: 24,
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
          background: `radial-gradient(circle, ${color}18 0%, transparent 70%)`,
          left: pos.x - 125,
          top: pos.y - 125,
          transition: 'left 50ms, top 50ms',
        }} />
      )}
      <div style={{ position: 'relative', zIndex: 1 }}>{children}</div>
    </div>
  )
}
