import React from "react"

type Variant = "primary" | "default" | "secondary" | "ghost" | "outline" | "danger" | "destructive" | "link"
type Size = "sm" | "md" | "lg" | "icon"

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent/80",
  default: "bg-accent text-white hover:bg-accent/80",  // shadcn alias for primary
  secondary: "bg-bg-2 text-white hover:bg-bg-3 border border-border/10",
  ghost: "text-muted hover:text-white hover:bg-bg-2",
  outline: "bg-transparent text-white border border-border/20 hover:bg-bg-2 hover:border-border/40",
  danger: "bg-transparent text-[color:var(--danger)] border border-[color:var(--danger)]/30 hover:bg-[color:var(--danger)]/10",
  destructive: "bg-[color:var(--danger)] text-white hover:bg-[color:var(--danger)]/80",  // shadcn
  link: "bg-transparent text-accent underline-offset-4 hover:underline p-0",
}

const SIZE_CLASS: Record<Size, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2",
  lg: "px-6 py-3 text-lg",
  icon: "p-2 aspect-square",
}

export function Button({ variant = "primary", size = "md", className = "", children, ...props }: ButtonProps) {
  const base = "rounded font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent/50 inline-flex items-center justify-center gap-2"
  return (
    <button className={`${base} ${VARIANT_CLASS[variant]} ${SIZE_CLASS[size]} ${className}`} {...props}>
      {children}
    </button>
  )
}

/** Icon-only button — square, no padding quirks. Alias of `<Button size="icon" variant="ghost">`. */
export function IconButton({ variant = "ghost", size = "icon", className = "", children, ...props }: ButtonProps) {
  return (
    <Button variant={variant} size={size} className={className} {...props}>
      {children}
    </Button>
  )
}

export default Button
