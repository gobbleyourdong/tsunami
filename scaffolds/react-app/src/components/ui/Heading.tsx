import React from "react"

type HeadingSize = "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "6xl" | "7xl"
type Weight = "normal" | "medium" | "semibold" | "bold" | "extrabold"

interface HeadingProps extends React.HTMLAttributes<HTMLHeadingElement> {
  level?: 1 | 2 | 3 | 4 | 5 | 6
  size?: HeadingSize
  as?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | string
  weight?: Weight
  color?: string
}

const SIZE: Record<HeadingSize, string> = {
  xs: "text-base",
  sm: "text-lg",
  md: "text-xl",
  lg: "text-2xl",
  xl: "text-3xl",
  "2xl": "text-4xl",
  "3xl": "text-5xl",
  "4xl": "text-6xl",
  "5xl": "text-7xl",
  "6xl": "text-8xl",
  "7xl": "text-9xl",
}

const WEIGHT: Record<Weight, string> = {
  normal: "font-normal",
  medium: "font-medium",
  semibold: "font-semibold",
  bold: "font-bold",
  extrabold: "font-extrabold",
}

const COLOR_CLASS: Record<string, string> = {
  primary: "text-accent",
  accent: "text-accent",
  muted: "text-muted",
  default: "text-fg",
  fg: "text-fg",
  white: "text-white",
}

export function Heading({ level = 2, size = "lg", as, weight = "bold", color, className = "", style, children, ...props }: HeadingProps) {
  const Tag = (as || `h${level}`) as any
  const colorCls = color ? COLOR_CLASS[color] ?? "" : ""
  const colorStyle: React.CSSProperties =
    color && !COLOR_CLASS[color] ? { color } : {}
  return (
    <Tag
      className={`${WEIGHT[weight]} tracking-tight ${SIZE[size]} ${colorCls} ${className}`}
      style={{ ...colorStyle, ...style }}
      {...props}
    >
      {children}
    </Tag>
  )
}

export default Heading
