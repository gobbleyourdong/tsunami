import { useEffect, useRef, useState, ReactNode } from "react"

interface ParallaxProps {
  children: ReactNode
  speed?: number  // 0.1 = slow, 1 = normal scroll, 2 = fast
  style?: React.CSSProperties
}

/** Parallax scrolling section — content moves at a different speed than scroll. */
export function Parallax({ children, speed = 0.5, style }: ParallaxProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const handler = () => {
      if (!ref.current) return
      const rect = ref.current.getBoundingClientRect()
      const center = rect.top + rect.height / 2
      const viewCenter = window.innerHeight / 2
      setOffset((center - viewCenter) * (1 - speed))
    }
    window.addEventListener("scroll", handler, { passive: true })
    handler()
    return () => window.removeEventListener("scroll", handler)
  }, [speed])

  return (
    <div ref={ref} style={{ overflow: "hidden", ...style }}>
      <div style={{ transform: `translateY(${offset}px)`, willChange: "transform" }}>
        {children}
      </div>
    </div>
  )
}

export default Parallax
