import React from "react"

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export default function Card({ className = "", children, ...props }: CardProps) {
  return (
    <div className={`bg-bg-1 rounded-lg border border-border/10 ${className}`} {...props}>
      {children}
    </div>
  )
}
