import { ReactNode } from "react"

interface MarqueeProps {
  children: ReactNode
  speed?: number  // seconds for one full cycle
  duration?: number  // alias drones reach for
  direction?: "left" | "right"
  pauseOnHover?: boolean
  gap?: number  // px between repeated children
}

/** CSS-only infinite scrolling marquee — logos, testimonials, etc. */
export function Marquee({ children, speed, duration, direction = "left", pauseOnHover = true, gap = 0 }: MarqueeProps) {
  const dir = direction === "left" ? "marquee-left" : "marquee-right"
  const sec = speed ?? duration ?? 20

  return (
    <div style={{ overflow: "hidden", width: "100%" }}>
      <style>{`
        @keyframes marquee-left { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        @keyframes marquee-right { from { transform: translateX(-50%); } to { transform: translateX(0); } }
      `}</style>
      <div style={{
        display: "flex", width: "max-content", gap,
        animation: `${dir} ${sec}s linear infinite`,
        ...(pauseOnHover ? {} : {}),
      }}
        onMouseEnter={e => pauseOnHover && (e.currentTarget.style.animationPlayState = "paused")}
        onMouseLeave={e => pauseOnHover && (e.currentTarget.style.animationPlayState = "running")}
      >
        {children}{children}
      </div>
    </div>
  )
}

export default Marquee
