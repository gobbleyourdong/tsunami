import { useEffect, useState, useRef } from "react"

interface AnimatedCounterProps {
  value: number
  duration?: number  // ms
  prefix?: string
  suffix?: string
  style?: React.CSSProperties
}

/** Animated number counter — scrolls from 0 to value. */
export default function AnimatedCounter({ value, duration = 1000, prefix = "", suffix = "", style }: AnimatedCounterProps) {
  const [display, setDisplay] = useState(0)
  const ref = useRef<HTMLDivElement>(null)
  const started = useRef(false)

  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && !started.current) {
        started.current = true
        const start = performance.now()
        const animate = (now: number) => {
          const progress = Math.min((now - start) / duration, 1)
          const eased = 1 - Math.pow(1 - progress, 3)  // ease-out cubic
          setDisplay(Math.round(eased * value))
          if (progress < 1) requestAnimationFrame(animate)
        }
        requestAnimationFrame(animate)
      }
    })
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [value, duration])

  return <span ref={ref} style={style}>{prefix}{display.toLocaleString()}{suffix}</span>
}
