interface StatCardProps {
  label: string
  value: string | number
  change?: string
  icon?: string
  color?: string
}

export default function StatCard({ label, value, change, icon, color }: StatCardProps) {
  const isPositive = change && !change.startsWith("-")

  return (
    <div className="card stat-card">
      <div className="flex-between">
        <span className="text-muted text-sm" style={{ textTransform: "uppercase", letterSpacing: 1 }}>
          {label}
        </span>
        {icon && <span style={{ fontSize: 20, opacity: 0.5 }}>{icon}</span>}
      </div>
      <div className="stat-value" style={color ? { color } : undefined}>{value}</div>
      {change && (
        <span className={`badge ${isPositive ? "positive" : "negative"}`}>
          {change}
        </span>
      )}
    </div>
  )
}
