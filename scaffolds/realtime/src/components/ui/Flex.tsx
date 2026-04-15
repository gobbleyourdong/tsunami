import React from "react"

interface FlexProps extends React.HTMLAttributes<HTMLDivElement> {
  direction?: "row" | "col"
  align?: "start" | "center" | "end" | "stretch"
  justify?: "start" | "center" | "end" | "between" | "around"
  gap?: 0 | 1 | 2 | 3 | 4 | 6 | 8
  wrap?: boolean
}

export function Flex({
  direction = "row",
  align,
  justify,
  gap = 0,
  wrap = false,
  className = "",
  children,
  ...props
}: FlexProps) {
  const cls = [
    "flex",
    direction === "col" ? "flex-col" : "flex-row",
    align ? `items-${align}` : "",
    justify ? `justify-${justify}` : "",
    gap ? `gap-${gap}` : "",
    wrap ? "flex-wrap" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ")
  return (
    <div className={cls} {...props}>
      {children}
    </div>
  )
}

export default Flex
