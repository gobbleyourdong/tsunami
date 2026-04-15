import { useEffect, useRef, useState, ReactNode } from "react"

interface ScrollRevealProps {
  children: ReactNode
  direction?: "up" | "down" | "left" | "right" | "fade"
  delay?: number     // ms
  duration?: number  // ms
  distance?: number  // px
  once?: boolean     // only animate once
}

/** Reveal content on scroll into viewport. */
export function ScrollReveal({
  children,
  direction = "up",
  delay = 0,
  duration = 600,
  distance = 30,
  once = true,
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          if (once) observer.disconnect()
        } else if (!once) {
          setVisible(false)
        }
      },
      { threshold: 0.1 }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [once])

  const transforms: Record<string, string> = {
    up: `translateY(${distance}px)`,
    down: `translateY(-${distance}px)`,
    left: `translateX(${distance}px)`,
    right: `translateX(-${distance}px)`,
    fade: "none",
  }

  return (
    <div ref={ref} style={{
      opacity: visible ? 1 : 0,
      transform: visible ? "none" : transforms[direction],
      transition: `opacity ${duration}ms ease ${delay}ms, transform ${duration}ms ease ${delay}ms`,
    }}>
      {children}
    </div>
  )
}

export default ScrollReveal
