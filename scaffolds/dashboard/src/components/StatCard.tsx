interface StatCardProps {
  label: string
  value: string | number
  change?: string
  color?: string
}

/** Big number stat display — "Revenue: $12.4K ↑ 12%" */
export default function StatCard({ label, value, change, color = "#0ff" }: StatCardProps) {
  return (
    <div style={{
      background: "#1a1a2e",
      borderRadius: 8,
      border: "1px solid #2a2a4a",
      padding: 20,
    }}>
      <div style={{ fontSize: 12, color: "#888", textTransform: "uppercase", letterSpacing: 1 }}>
        {label}
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, color, marginTop: 4 }}>
        {value}
      </div>
      {change && (
        <div style={{ fontSize: 13, color: change.startsWith("-") ? "#f44" : "#4f4", marginTop: 4 }}>
          {change}
        </div>
      )}
    </div>
  )
}
