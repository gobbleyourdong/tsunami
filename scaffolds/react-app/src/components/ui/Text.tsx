import React from "react"

interface TextProps extends React.HTMLAttributes<HTMLSpanElement> {
  as?: "span" | "p" | "div"
}

export default function Text({ as = "span", className = "", children, ...props }: TextProps) {
  const Tag = as as any
  return (
    <Tag className={`text-base text-fg ${className}`} {...props}>
      {children}
    </Tag>
  )
}
