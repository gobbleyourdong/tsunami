import React from "react"

interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  maxHeight?: string | number
  orientation?: "vertical" | "horizontal" | "both"
}

/**
 * Scrollable container with styled thin scrollbars that match the design
 * system (see ::-webkit-scrollbar rules in index.css). shadcn/Radix convention.
 */
export function ScrollArea({
  maxHeight = 400,
  orientation = "vertical",
  className = "",
  style,
  children,
  ...props
}: ScrollAreaProps) {
  const overflow =
    orientation === "horizontal"
      ? { overflowX: "auto" as const, overflowY: "hidden" as const }
      : orientation === "both"
      ? { overflow: "auto" as const }
      : { overflowX: "hidden" as const, overflowY: "auto" as const }

  return (
    <div
      className={className}
      style={{
        maxHeight,
        ...overflow,
        scrollbarWidth: "thin",
        scrollbarColor: "var(--bg-4) transparent",
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  )
}

export default ScrollArea
