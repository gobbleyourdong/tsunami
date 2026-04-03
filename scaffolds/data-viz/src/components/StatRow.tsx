interface Stat {
  label: string
  value: string | number
  change?: string
}

interface StatRowProps {
  stats: Stat[]
}

/** Row of stat cards — use at the top of a data viz page */
export default function StatRow({ stats }: StatRowProps) {
  return (
    <div className="stat-row">
      {stats.map((s, i) => (
        <div key={i} className="stat-item">
          <span className="stat-label">{s.label}</span>
          <span className="stat-value">{s.value}</span>
          {s.change && (
            <span className={`stat-change ${s.change.startsWith("-") ? "negative" : "positive"}`}>
              {s.change}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
