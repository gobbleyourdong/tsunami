import { useEffect, useState, useRef } from "react"

type CounterFormat = "number" | "compact" | "currency" | "percent"

interface AnimatedCounterProps {
  value?: number       // target value (preferred)
  to?: number          // alias for value
  from?: number        // start value (default 0)
  duration?: number    // ms
  prefix?: string
  suffix?: string
  precision?: number   // decimal places
  format?: CounterFormat
  className?: string
  style?: React.CSSProperties
}

function fmt(n: number, format: CounterFormat | undefined, precision: number): string {
  if (format === "compact") return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n)
  if (format === "currency") return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: precision }).format(n)
  if (format === "percent") return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: precision }).format(n)
  return precision > 0
    ? n.toLocaleString(undefined, { minimumFractionDigits: precision, maximumFractionDigits: precision })
    : Math.round(n).toLocaleString()
}

/** Animated number counter — scrolls from `from` (default 0) to `value`/`to`. */
export function AnimatedCounter({
  value,
  to,
  from = 0,
  duration = 1000,
  prefix = "",
  suffix = "",
  precision = 0,
  format,
  className = "",
  style,
}: AnimatedCounterProps) {
  const target = value ?? to ?? 0
  const [display, setDisplay] = useState(from)
  const ref = useRef<HTMLSpanElement>(null)
  const started = useRef(false)

  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && !started.current) {
        started.current = true
        const start = performance.now()
        const animate = (now: number) => {
          const progress = Math.min((now - start) / duration, 1)
          const eased = 1 - Math.pow(1 - progress, 3)  // ease-out cubic
          setDisplay(from + (target - from) * eased)
          if (progress < 1) requestAnimationFrame(animate)
          else setDisplay(target)
        }
        requestAnimationFrame(animate)
      }
    })
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [target, from, duration])

  return <span ref={ref} className={className} style={style}>{prefix}{fmt(display, format, precision)}{suffix}</span>
}

export default AnimatedCounter
