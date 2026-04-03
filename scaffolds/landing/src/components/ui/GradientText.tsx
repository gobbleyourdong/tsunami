import { ReactNode } from "react"

interface GradientTextProps {
  children: ReactNode
  from?: string
  to?: string
  via?: string
  animate?: boolean
  style?: React.CSSProperties
}

export default function GradientText({
  children,
  from = "#4a9eff",
  to = "#60a0f0",
  via,
  animate = false,
  style,
}: GradientTextProps) {
  const gradient = via
    ? `linear-gradient(90deg, ${from}, ${via}, ${to})`
    : `linear-gradient(90deg, ${from}, ${to})`

  return (
    <span style={{
      background: animate ? `linear-gradient(90deg, ${from}, ${to}, ${from})` : gradient,
      backgroundSize: animate ? '200% auto' : 'auto',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      backgroundClip: 'text',
      animation: animate ? 'gradient-shift 3s linear infinite' : 'none',
      ...style,
    }}>
      {animate && <style>{`@keyframes gradient-shift { to { background-position: 200% center; } }`}</style>}
      {children}
    </span>
  )
}
