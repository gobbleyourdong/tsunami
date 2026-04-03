interface StatCardProps {
  label: string
  value: string | number
  change?: string
  icon?: string
  trend?: "up" | "down" | "flat"
}

export default function StatCard({ label, value, change, icon, trend }: StatCardProps) {
  const isPositive = trend === "up" || (change && !change.startsWith("-"))

  return (
    <div className="card stat-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span className="stat-label">{label}</span>
        {icon && <span style={{ fontSize: 20, opacity: 0.4 }}>{icon}</span>}
      </div>
      <div className="stat-value">{value}</div>
      {change && (
        <span className={`stat-change ${isPositive ? 'up' : 'down'}`}>
          {isPositive ? '↑' : '↓'} {change}
        </span>
      )}
    </div>
  )
}
