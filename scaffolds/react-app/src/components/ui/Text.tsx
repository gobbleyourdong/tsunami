import React from "react"

type TextSize = "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "6xl"

interface TextProps extends React.HTMLAttributes<HTMLSpanElement> {
  as?: "span" | "p" | "div" | "label" | "small"
  size?: TextSize
  muted?: boolean
  weight?: "normal" | "medium" | "semibold" | "bold"
  color?: string
}

const SIZE: Record<TextSize, string> = {
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
}

const WEIGHT: Record<NonNullable<TextProps["weight"]>, string> = {
  normal: "font-normal",
  medium: "font-medium",
  semibold: "font-semibold",
  bold: "font-bold",
}

const COLOR_CLASS: Record<string, string> = {
  primary: "text-accent",
  accent: "text-accent",
  muted: "text-muted",
  default: "text-fg",
  fg: "text-fg",
  white: "text-white",
}

export function Text({
  as = "span",
  size = "md",
  muted = false,
  weight,
  color,
  className = "",
  style,
  children,
  ...props
}: TextProps) {
  const Tag = as as any
  const colorCls = color ? COLOR_CLASS[color] ?? "" : ""
  const colorStyle: React.CSSProperties =
    color && !COLOR_CLASS[color] ? { color } : {}
  const cls = [
    SIZE[size],
    !color ? (muted ? "text-muted" : "text-fg") : colorCls,
    color && muted ? "" : "",
    weight ? WEIGHT[weight] : "",
    className,
  ]
    .filter(Boolean)
    .join(" ")
  return (
    <Tag className={cls} style={{ ...colorStyle, ...style }} {...props}>
      {children}
    </Tag>
  )
}

export default Text
