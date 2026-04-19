import React from "react"

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated" | "outline" | "ghost" | "filled"
  padding?: "none" | "sm" | "md" | "lg" | "xl" | number
  hoverable?: boolean
  interactive?: boolean
  bordered?: boolean
}

const VARIANT: Record<NonNullable<CardProps["variant"]>, string> = {
  default: "bg-bg-1 border border-border/10",
  elevated: "bg-bg-1 border border-border/10 shadow-lg",
  outline: "bg-transparent border border-border/20",
  ghost: "bg-transparent",
  filled: "bg-bg-2 border border-border/10",
}

const PAD: Record<string, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
  xl: "p-8",
}

export function Card({
  variant = "default",
  padding,
  hoverable = false,
  interactive = false,
  bordered,
  className = "",
  children,
  ...props
}: CardProps) {
  const padCls =
    padding == null ? "" : typeof padding === "number" ? `` : PAD[padding] ?? ""
  const padStyle: React.CSSProperties =
    typeof padding === "number" ? { padding: padding * 4 } : {}
  const hoverCls = hoverable || interactive ? "transition-colors hover:border-border/30" : ""
  const cursorCls = interactive ? "cursor-pointer" : ""
  const borderOverride = bordered === false ? "border-0" : ""
  return (
    <div
      className={`rounded-lg ${VARIANT[variant]} ${padCls} ${hoverCls} ${cursorCls} ${borderOverride} ${className}`}
      style={{ ...padStyle, ...props.style }}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ className = "", children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`px-6 py-4 border-b border-border/10 ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardTitle({ className = "", children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={`text-lg font-semibold ${className}`} {...props}>
      {children}
    </h3>
  )
}

export function CardDescription({ className = "", children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={`text-sm text-muted ${className}`} {...props}>
      {children}
    </p>
  )
}

export function CardContent({ className = "", children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`px-6 py-4 ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardFooter({ className = "", children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`px-6 py-4 border-t border-border/10 flex items-center ${className}`} {...props}>
      {children}
    </div>
  )
}

export default Card
