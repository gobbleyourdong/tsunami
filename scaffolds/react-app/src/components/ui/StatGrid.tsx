import React from "react"
import MetricCard from "./MetricCard"

interface Stat {
  label: string
  value: React.ReactNode
  delta?: number
  deltaLabel?: string
  prefix?: string
  suffix?: string
  hint?: string
  icon?: React.ReactNode
  invertDelta?: boolean
}

interface StatGridProps {
  stats?: Stat[]
  columns?: number
  minWidth?: number
  gap?: number
  children?: React.ReactNode
  className?: string
  style?: React.CSSProperties
}

export default function StatGrid({
  stats,
  columns,
  minWidth = 220,
  gap = 16,
  children,
  className = "",
  style,
}: StatGridProps) {
  const gridTemplate = columns
    ? `repeat(${columns}, minmax(0, 1fr))`
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
      {stats?.map((s, i) => <MetricCard key={i} {...s} />)}
      {children}
    </div>
  )
}
