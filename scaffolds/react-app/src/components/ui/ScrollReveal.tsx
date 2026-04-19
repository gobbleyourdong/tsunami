import { useEffect, useRef, useState, ReactNode } from "react"

type RevealDirection = "up" | "down" | "left" | "right" | "fade"

interface ScrollRevealProps {
  children: ReactNode
  direction?: RevealDirection
  animation?: RevealDirection | "slide-up" | "slide-down" | "slide-left" | "slide-right" | "fade-in"
  delay?: number     // ms
  duration?: number  // ms
  distance?: number  // px
  once?: boolean     // only animate once
  className?: string
}

const ANIM_TO_DIR: Record<string, RevealDirection> = {
  "slide-up": "up",
  "slide-down": "down",
  "slide-left": "left",
  "slide-right": "right",
  "fade-in": "fade",
  up: "up", down: "down", left: "left", right: "right", fade: "fade",
}

/** Reveal content on scroll into viewport. */
export function ScrollReveal({
  children,
  direction,
  animation,
  delay = 0,
  duration = 600,
  distance = 30,
  once = true,
  className,
}: ScrollRevealProps) {
  const dir: RevealDirection = direction ?? (animation ? ANIM_TO_DIR[animation] ?? "up" : "up")
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
    <div ref={ref} className={className} style={{
      opacity: visible ? 1 : 0,
      transform: visible ? "none" : transforms[dir],
      transition: `opacity ${duration}ms ease ${delay}ms, transform ${duration}ms ease ${delay}ms`,
    }}>
      {children}
    </div>
  )
}

export default ScrollReveal
