import { useEffect, useRef, useState } from "react"

interface Stat {
  value: string
  label: string
}

interface StatsRowProps {
  stats: Stat[]
}

/** Animated counter that counts up when scrolled into view. */
function AnimatedStat({ value, label }: Stat) {
  const ref = useRef<HTMLDivElement>(null)
  const [display, setDisplay] = useState("0")

  useEffect(() => {
    if (!ref.current) return
    const obs = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      obs.disconnect()

      // Parse numeric part and suffix (e.g. "10K+" → 10, "K+")
      const match = value.match(/^([\d.]+)(.*)$/)
      if (!match) { setDisplay(value); return }

      const target = parseFloat(match[1])
      const suffix = match[2]
      const duration = 1200
      const start = performance.now()

      const tick = (now: number) => {
        const elapsed = now - start
        const progress = Math.min(elapsed / duration, 1)
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3)
        const current = target * eased

        setDisplay(
          (Number.isInteger(target) ? Math.round(current) : current.toFixed(1)) + suffix
        )
        if (progress < 1) requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    }, { threshold: 0.3 })
    obs.observe(ref.current)
    return () => obs.disconnect()
  }, [value])

  return (
    <div ref={ref} style={{ textAlign: 'center', flex: 1, minWidth: 120 }}>
      <div style={{
        fontSize: 'var(--text-2xl)',
        fontWeight: 800,
        color: 'var(--accent)',
        letterSpacing: '-0.02em',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {display}
      </div>
      <div style={{
        fontSize: 'var(--text-sm)',
        color: 'var(--text-muted)',
        marginTop: 4,
        fontWeight: 500,
      }}>
        {label}
      </div>
    </div>
  )
}

export default function StatsRow({ stats }: StatsRowProps) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      gap: 48,
      flexWrap: 'wrap',
      padding: '40px 0',
    }}>
      {stats.map((s, i) => (
        <AnimatedStat key={i} {...s} />
      ))}
    </div>
  )
}
