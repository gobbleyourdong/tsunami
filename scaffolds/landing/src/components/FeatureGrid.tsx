interface Feature {
  title: string
  description: string
  icon?: string
}

interface FeatureGridProps {
  features: Feature[]
  columns?: number
}

export default function FeatureGrid({ features, columns = 3 }: FeatureGridProps) {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: `repeat(auto-fit, minmax(${Math.floor(800 / columns)}px, 1fr))`,
      gap: 24,
    }}>
      {features.map((f, i) => (
        <div key={i} style={{
          background: "#1a1a2e", borderRadius: 12, padding: 24,
          border: "1px solid #2a2a4a",
        }}>
          {f.icon && <div style={{ fontSize: 32, marginBottom: 12 }}>{f.icon}</div>}
          <h3 style={{ fontSize: 18, fontWeight: 600, color: "#fff", marginBottom: 8 }}>{f.title}</h3>
          <p style={{ fontSize: 14, color: "#888", lineHeight: 1.6 }}>{f.description}</p>
        </div>
      ))}
    </div>
  )
}
