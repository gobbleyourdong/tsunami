import React from "react"

interface TextProps extends React.HTMLAttributes<HTMLSpanElement> {
  as?: "span" | "p" | "div"
  size?: "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl"
  muted?: boolean
  weight?: "normal" | "medium" | "semibold" | "bold"
}

const SIZE: Record<NonNullable<TextProps["size"]>, string> = {
  xs: "text-xs",
  sm: "text-sm",
  md: "text-base",
  lg: "text-lg",
  xl: "text-xl",
  "2xl": "text-2xl",
  "3xl": "text-3xl",
}

const WEIGHT: Record<NonNullable<TextProps["weight"]>, string> = {
  normal: "font-normal",
  medium: "font-medium",
  semibold: "font-semibold",
  bold: "font-bold",
}

export function Text({
  as = "span",
  size = "md",
  muted = false,
  weight,
  className = "",
  children,
  ...props
}: TextProps) {
  const Tag = as as any
  const cls = [
    SIZE[size],
    muted ? "text-muted" : "text-fg",
    weight ? WEIGHT[weight] : "",
    className,
  ]
    .filter(Boolean)
    .join(" ")
  return (
    <Tag className={cls} {...props}>
      {children}
    </Tag>
  )
}

export default Text
