import React from "react"

type BadgeVariant =
  | "default" | "primary" | "secondary" | "outline"
  | "success" | "warning" | "destructive" | "danger" | "info" | "ghost"
type BadgeSize = "xs" | "sm" | "md" | "lg"

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  size?: BadgeSize
  color?: string
  pill?: boolean
  outline?: boolean
  dot?: boolean
  status?: "online" | "offline" | "away" | "busy" | string
}

const VARIANT_CLASS: Record<BadgeVariant, string> = {
  default: "bg-accent/15 text-accent",
  primary: "bg-accent/15 text-accent",
  secondary: "bg-bg-2 text-fg",
  outline: "bg-transparent text-fg border border-border/30",
  success: "bg-[rgba(52,212,176,0.15)] text-[color:var(--success)]",
  warning: "bg-[rgba(240,176,64,0.15)] text-[color:var(--warning)]",
  destructive: "bg-[rgba(240,96,96,0.15)] text-[color:var(--danger)]",
  danger: "bg-[rgba(240,96,96,0.15)] text-[color:var(--danger)]",
  info: "bg-accent/15 text-accent",
  ghost: "bg-transparent text-muted",
}

const SIZE_CLASS: Record<BadgeSize, string> = {
  xs: "px-1.5 py-0 text-[10px]",
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-0.5 text-sm",
  lg: "px-3 py-1 text-sm",
}

const STATUS_COLORS: Record<string, string> = {
  online: "var(--success, #34d4b0)",
  offline: "var(--text-dim, #4a4f5e)",
  away: "var(--warning, #f0b040)",
  busy: "var(--danger, #f06060)",
}

export function Badge({
  variant = "default",
  size = "sm",
  color,
  pill = true,
  outline = false,
  dot = false,
  status,
  className = "",
  style,
  children,
  ...props
}: BadgeProps) {
  const variantCls = outline ? "bg-transparent border border-current" : VARIANT_CLASS[variant]
  const radius = pill ? "rounded-full" : "rounded"
  const colorStyle: React.CSSProperties = color ? { color, background: `${color}26` } : {}
  const dotColor = status ? STATUS_COLORS[status] ?? status : color ?? "currentColor"
  return (
    <span
      className={`inline-flex items-center gap-1 ${SIZE_CLASS[size]} ${radius} font-medium ${variantCls} ${className}`}
      style={{ ...colorStyle, ...style }}
      {...props}
    >
      {(dot || status) && (
        <span
          aria-hidden
          style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor, display: "inline-block" }}
        />
      )}
      {children}
    </span>
  )
}

export default Badge
