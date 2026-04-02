import { ReactNode } from "react"

interface MarqueeProps {
  children: ReactNode
  speed?: number  // seconds for one full cycle
  direction?: "left" | "right"
  pauseOnHover?: boolean
}

/** CSS-only infinite scrolling marquee — logos, testimonials, etc. */
export default function Marquee({ children, speed = 20, direction = "left", pauseOnHover = true }: MarqueeProps) {
  const dir = direction === "left" ? "marquee-left" : "marquee-right"

  return (
    <div style={{ overflow: "hidden", width: "100%" }}>
      <style>{`
        @keyframes marquee-left { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        @keyframes marquee-right { from { transform: translateX(-50%); } to { transform: translateX(0); } }
      `}</style>
      <div style={{
        display: "flex", width: "max-content",
        animation: `${dir} ${speed}s linear infinite`,
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
