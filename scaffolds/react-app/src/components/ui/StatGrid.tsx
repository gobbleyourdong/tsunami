import React from "react"
import MetricCard from "./MetricCard"

interface Stat {
  label?: string
  title?: string
  value: React.ReactNode
  delta?: number
  change?: number
  trend?: "up" | "down" | "neutral" | "flat"
  deltaLabel?: string
  prefix?: string
  suffix?: string
  hint?: string
  icon?: React.ReactNode
  invertDelta?: boolean
}

interface StatGridProps {
  stats?: Stat[]
  items?: Stat[]  // alias for stats
  columns?: number
  cols?: number   // alias for columns
  minWidth?: number
  gap?: number
  children?: React.ReactNode
  className?: string
  style?: React.CSSProperties
}

export function StatGrid({
  stats,
  items,
  columns,
  cols,
  minWidth = 220,
  gap = 16,
  children,
  className = "",
  style,
}: StatGridProps) {
  const list = stats ?? items
  const ncols = columns ?? cols
  const gridTemplate = ncols
    ? `repeat(${ncols}, minmax(0, 1fr))`
    : `repeat(auto-fill, minmax(${minWidth}px, 1fr))`

  return (
    <div
      className={className}
      style={{
        display: "grid",
        gridTemplateColumns: gridTemplate,
        gap,
        width: "100%",
        ...style,
      }}
    >
      {list?.map((s, i) => <MetricCard key={i} {...s} />)}
      {children}
    </div>
  )
}

export default StatGrid
