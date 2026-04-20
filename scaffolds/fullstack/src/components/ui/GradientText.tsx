import { ReactNode, ElementType } from "react"

interface GradientTextProps {
  children: ReactNode
  from?: string
  to?: string
  via?: string
  animate?: boolean
  style?: React.CSSProperties
  className?: string
  as?: ElementType
  size?: "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "6xl" | "7xl" | "8xl" | "9xl"
  [key: string]: any
}

const GT_SIZE: Record<NonNullable<GradientTextProps["size"]>, string> = {
  xs: "text-xs",
  sm: "text-sm",
  md: "text-base",
  lg: "text-lg",
  xl: "text-xl",
  "2xl": "text-2xl",
  "3xl": "text-3xl",
  "4xl": "text-4xl",
  "5xl": "text-5xl",
  "6xl": "text-6xl",
  "7xl": "text-7xl",
  "8xl": "text-8xl",
  "9xl": "text-9xl",
}

export function GradientText({
  children,
  from = "#4a9eff",
  to = "#60a0f0",
  via,
  animate = false,
  style,
  className = "",
  as,
  size,
  ...rest
}: GradientTextProps) {
  const Tag = (as ?? "span") as any
  const sizeCls = size ? GT_SIZE[size] : ""
  const cls = [sizeCls, className].filter(Boolean).join(" ")
  const gradient = via
    ? `linear-gradient(90deg, ${from}, ${via}, ${to})`
    : `linear-gradient(90deg, ${from}, ${to})`

  return (
    <Tag {...rest} className={cls} style={{
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
    </Tag>
  )
}

export default GradientText
