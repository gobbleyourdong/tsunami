import React from "react"

interface ScrollAreaProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "height"> {
  maxHeight?: string | number
  height?: string | number  // alias drones reach for
  orientation?: "vertical" | "horizontal" | "both"
}

/**
 * Scrollable container with styled thin scrollbars that match the design
 * system (see ::-webkit-scrollbar rules in index.css). shadcn/Radix convention.
 */
export function ScrollArea({
  maxHeight,
  height,
  orientation = "vertical",
  className = "",
  style,
  children,
  ...props
}: ScrollAreaProps) {
  const cap = maxHeight ?? height ?? 400
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
        maxHeight: cap,
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
