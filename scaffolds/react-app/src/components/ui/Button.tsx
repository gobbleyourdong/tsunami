import React from "react"

type Variant =
  | "primary" | "default" | "secondary" | "ghost" | "outline"
  | "danger" | "destructive" | "link"
  | "solid" | "subtle" | "soft"
type Size = "xs" | "sm" | "md" | "lg" | "xl" | "icon"

interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "size"> {
  variant?: Variant
  size?: Size
  loading?: boolean
  fullWidth?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent/80",
  default: "bg-accent text-white hover:bg-accent/80",
  secondary: "bg-bg-2 text-white hover:bg-bg-3 border border-border/10",
  ghost: "text-muted hover:text-white hover:bg-bg-2",
  outline: "bg-transparent text-white border border-border/20 hover:bg-bg-2 hover:border-border/40",
  danger: "bg-transparent text-[color:var(--danger)] border border-[color:var(--danger)]/30 hover:bg-[color:var(--danger)]/10",
  destructive: "bg-[color:var(--danger)] text-white hover:bg-[color:var(--danger)]/80",
  link: "bg-transparent text-accent underline-offset-4 hover:underline p-0",
  solid: "bg-accent text-white hover:bg-accent/80",  // alias for primary
  subtle: "bg-accent/10 text-accent hover:bg-accent/20",
  soft: "bg-accent/15 text-accent hover:bg-accent/25",
}

const SIZE_CLASS: Record<Size, string> = {
  xs: "px-2 py-1 text-xs",
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2",
  lg: "px-6 py-3 text-lg",
  xl: "px-8 py-4 text-xl",
  icon: "p-2 aspect-square",
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  loading = false,
  disabled,
  fullWidth = false,
  leftIcon,
  rightIcon,
  children,
  ...props
}: ButtonProps) {
  const base = "rounded font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent/50 inline-flex items-center justify-center gap-2"
  const widthCls = fullWidth ? "w-full" : ""
  const disabledCls = disabled || loading ? "opacity-60 cursor-not-allowed" : ""
  return (
    <button
      className={`${base} ${VARIANT_CLASS[variant]} ${SIZE_CLASS[size]} ${widthCls} ${disabledCls} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <span aria-hidden style={{ display: "inline-block", width: 12, height: 12, border: "2px solid currentColor", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />}
      {!loading && leftIcon && <span aria-hidden style={{ display: "inline-flex" }}>{leftIcon}</span>}
      {children}
      {!loading && rightIcon && <span aria-hidden style={{ display: "inline-flex" }}>{rightIcon}</span>}
    </button>
  )
}

export function IconButton({ variant = "ghost", size = "icon", className = "", children, ...props }: ButtonProps) {
  return (
    <Button variant={variant} size={size} className={className} {...props}>
      {children}
    </Button>
  )
}

export default Button
