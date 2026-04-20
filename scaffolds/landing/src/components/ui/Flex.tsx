import React from "react"

interface FlexProps extends React.HTMLAttributes<HTMLDivElement> {
  direction?: "row" | "col" | "column" | "row-reverse" | "col-reverse" | "column-reverse"
  align?: "start" | "center" | "end" | "stretch" | "baseline"
  justify?: "start" | "center" | "end" | "between" | "around" | "evenly"
  gap?: number
  spacing?: number  // Mantine-style alias for gap
  wrap?: boolean
  inline?: boolean
}

const DIR: Record<string, string> = {
  row: "flex-row",
  "row-reverse": "flex-row-reverse",
  col: "flex-col",
  column: "flex-col",
  "col-reverse": "flex-col-reverse",
  "column-reverse": "flex-col-reverse",
}

export function Flex({
  direction = "row",
  align,
  justify,
  gap,
  spacing,
  wrap = false,
  inline = false,
  className = "",
  children,
  ...props
}: FlexProps) {
  const g = gap ?? spacing ?? 0
  const cls = [
    inline ? "inline-flex" : "flex",
    DIR[direction] ?? "flex-row",
    align ? `items-${align}` : "",
    justify ? `justify-${justify}` : "",
    g ? `gap-${g}` : "",
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
