import React from "react"

interface BoxProps extends React.HTMLAttributes<HTMLDivElement> {
  padding?: number | string
  p?: number | string
  margin?: number | string
  m?: number | string
  bg?: string
  bordered?: boolean
  rounded?: boolean | number | string
  shadow?: boolean | "sm" | "md" | "lg"
  gap?: number
}

const SPACE: Record<string, string> = { "1": "0.25rem", "2": "0.5rem", "3": "0.75rem", "4": "1rem", "6": "1.5rem", "8": "2rem" }
const space = (v: number | string | undefined): string | undefined => {
  if (v == null) return undefined
  if (typeof v === "number") return `${v * 0.25}rem`
  return SPACE[v] ?? v
}

export function Box({
  padding, p, margin, m, bg, bordered, rounded, shadow, gap,
  className = "", style, children, ...props
}: BoxProps) {
  const merged: React.CSSProperties = {
    ...(padding != null || p != null ? { padding: space(padding ?? p) } : {}),
    ...(margin != null || m != null ? { margin: space(margin ?? m) } : {}),
    ...(bg ? { background: bg.startsWith("#") || bg.startsWith("rgb") || bg.startsWith("var") ? bg : `var(--${bg}, ${bg})` } : {}),
    ...(bordered ? { border: "1px solid var(--border, rgba(255,255,255,0.06))" } : {}),
    ...(rounded ? { borderRadius: typeof rounded === "boolean" ? "var(--radius, 10px)" : typeof rounded === "number" ? rounded : rounded } : {}),
    ...(shadow ? { boxShadow: "0 4px 12px rgba(0,0,0,0.3)" } : {}),
    ...(gap != null ? { gap: space(gap) } : {}),
    ...style,
  }
  return (
    <div className={className} style={merged} {...props}>
      {children}
    </div>
  )
}

export default Box
