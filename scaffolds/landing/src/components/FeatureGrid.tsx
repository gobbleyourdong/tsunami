import { useEffect, useRef, useState } from "react"

interface Feature {
  title: string
  description: string
  icon?: string
}

interface FeatureGridProps {
  features: Feature[]
  columns?: 2 | 3 | 4
}

/** Scroll-triggered staggered entrance. Each card fades up on viewport entry. */
function useInView(ref: React.RefObject<HTMLElement | null>) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (!ref.current) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect() } },
      { threshold: 0.15 }
    )
    obs.observe(ref.current)
    return () => obs.disconnect()
  }, [ref])
  return visible
}

function FeatureCard({ feature, delay }: { feature: Feature; delay: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const visible = useInView(ref)

  return (
    <div
      ref={ref}
      className="feature-card"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(24px)',
        transition: `opacity 0.6s cubic-bezier(0.16,1,0.3,1) ${delay}ms, transform 0.6s cubic-bezier(0.16,1,0.3,1) ${delay}ms`,
      }}
    >
      {feature.icon && <div className="feature-icon">{feature.icon}</div>}
      <h3 className="feature-title">{feature.title}</h3>
      <p className="feature-desc">{feature.description}</p>
    </div>
  )
}

export default function FeatureGrid({ features, columns = 3 }: FeatureGridProps) {
  return (
    <div className={`feature-grid grid-${columns}`}>
      {features.map((f, i) => (
        <FeatureCard key={i} feature={f} delay={i * 100} />
      ))}
    </div>
  )
}
