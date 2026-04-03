interface Feature {
  title: string
  description: string
  icon?: string
}

interface FeatureGridProps {
  features: Feature[]
  columns?: 2 | 3 | 4
}

export default function FeatureGrid({ features, columns = 3 }: FeatureGridProps) {
  return (
    <div className={`feature-grid grid-${columns}`}>
      {features.map((f, i) => (
        <div key={i} className="feature-card">
          {f.icon && <div className="feature-icon">{f.icon}</div>}
          <h3 className="feature-title">{f.title}</h3>
          <p className="feature-desc">{f.description}</p>
        </div>
      ))}
    </div>
  )
}
