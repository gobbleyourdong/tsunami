import React from "react"

type InputSize = "sm" | "md" | "lg"

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size" | "prefix"> {
  label?: string
  error?: string
  helperText?: string
  size?: InputSize
  prefix?: React.ReactNode
  suffix?: React.ReactNode
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  fullWidth?: boolean
}

const SIZE_CLS: Record<InputSize, string> = {
  sm: "px-2.5 py-1.5 text-sm",
  md: "px-3 py-2",
  lg: "px-4 py-3 text-lg",
}

export function Input({
  label,
  error,
  helperText,
  size = "md",
  prefix,
  suffix,
  leftIcon,
  rightIcon,
  className = "",
  fullWidth = true,
  ...props
}: InputProps) {
  const hasAdornment = !!(prefix || suffix || leftIcon || rightIcon)
  const baseInput =
    `bg-bg-2 border rounded text-white placeholder:text-muted/50 ` +
    `focus:outline-none focus:ring-2 focus:ring-accent/50 ` +
    `${error ? "border-[color:var(--danger)]/60" : "border-border/10"}`
  const widthCls = fullWidth ? "w-full" : ""

  const inputEl = (
    <input
      className={`${baseInput} ${SIZE_CLS[size]} ${widthCls} ${hasAdornment ? "border-0 bg-transparent focus:ring-0 px-0" : ""} ${className}`}
      {...props}
    />
  )

  return (
    <div className={`flex flex-col gap-1 ${widthCls}`}>
      {label && <label className="text-sm text-muted">{label}</label>}
      {hasAdornment ? (
        <div className={`flex items-center gap-2 ${baseInput} ${SIZE_CLS[size]} ${widthCls}`}>
          {leftIcon && <span className="inline-flex">{leftIcon}</span>}
          {prefix && <span className="text-muted text-sm">{prefix}</span>}
          {inputEl}
          {suffix && <span className="text-muted text-sm">{suffix}</span>}
          {rightIcon && <span className="inline-flex">{rightIcon}</span>}
        </div>
      ) : (
        inputEl
      )}
      {error && <span className="text-xs text-[color:var(--danger)]">{error}</span>}
      {!error && helperText && <span className="text-xs text-muted">{helperText}</span>}
    </div>
  )
}

export default Input
