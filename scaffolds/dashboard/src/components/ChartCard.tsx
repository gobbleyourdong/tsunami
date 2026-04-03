import { ReactNode } from "react"

interface ChartCardProps {
  title: string
  subtitle?: string
  children: ReactNode
  action?: ReactNode
  height?: number
}

/** Wrapper for charts (recharts, etc.) with consistent header styling. */
export default function ChartCard({ title, subtitle, children, action, height = 300 }: ChartCardProps) {
  return (
    <div className="chart-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <div className="chart-title">{title}</div>
          {subtitle && (
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', marginTop: 2 }}>
              {subtitle}
            </div>
          )}
        </div>
        {action}
      </div>
      <div style={{ height, width: '100%' }}>
        {children}
      </div>
    </div>
  )
}
