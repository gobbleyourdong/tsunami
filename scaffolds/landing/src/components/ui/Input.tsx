import React from "react"

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export default function Input({ label, className = "", ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-sm text-muted">{label}</label>}
      <input
        className={`bg-bg-2 border border-border/10 rounded px-3 py-2 text-white placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/50 ${className}`}
        {...props}
      />
    </div>
  )
}
