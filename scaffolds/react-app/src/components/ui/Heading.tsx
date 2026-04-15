import React from "react"

interface HeadingProps extends React.HTMLAttributes<HTMLHeadingElement> {
  level?: 1 | 2 | 3 | 4 | 5 | 6
  size?: "sm" | "md" | "lg" | "xl" | "2xl" | "3xl"
}

const SIZE: Record<NonNullable<HeadingProps["size"]>, string> = {
  sm: "text-lg",
  md: "text-xl",
  lg: "text-2xl",
  xl: "text-3xl",
  "2xl": "text-4xl",
  "3xl": "text-5xl",
}

export function Heading({ level = 2, size = "lg", className = "", children, ...props }: HeadingProps) {
  const Tag = `h${level}` as any
  return (
    <Tag className={`font-bold tracking-tight ${SIZE[size]} ${className}`} {...props}>
      {children}
    </Tag>
  )
}

export default Heading
