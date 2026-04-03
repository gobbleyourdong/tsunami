import { ReactNode } from "react"

interface ChartCardProps {
  title: string
  subtitle?: string
  children: ReactNode
  height?: number
}

/** Styled container for any chart — handles title, spacing, responsive height */
export default function ChartCard({ title, subtitle, children, height = 300 }: ChartCardProps) {
  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3 className="chart-title">{title}</h3>
        {subtitle && <span className="chart-subtitle">{subtitle}</span>}
      </div>
      <div className="chart-body" style={{ height }}>
        {children}
      </div>
    </div>
  )
}
