import { useEffect, useRef, useState, ReactNode } from "react"

interface ParallaxHeroProps {
  bgImage?: string
  bgColor?: string
  height?: string
  children: ReactNode
  speed?: number
  overlay?: boolean
}

/** Full-screen parallax hero with optional background image and dark overlay. */
export default function ParallaxHero({
  bgImage,
  bgColor = "#0a0a1a",
  height = "100vh",
  children,
  speed = 0.4,
  overlay = true,
}: ParallaxHeroProps) {
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const handler = () => setOffset(window.scrollY * speed)
    window.addEventListener("scroll", handler, { passive: true })
    return () => window.removeEventListener("scroll", handler)
  }, [speed])

  return (
    <section style={{
      position: "relative", height, overflow: "hidden",
      display: "flex", alignItems: "center", justifyContent: "center",
      background: bgColor,
    }}>
      {bgImage && (
        <div style={{
          position: "absolute", inset: 0,
          backgroundImage: `url(${bgImage})`,
          backgroundSize: "cover", backgroundPosition: "center",
          transform: `translateY(${offset}px)`,
          willChange: "transform",
        }} />
      )}
      {overlay && <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.5)" }} />}
      <div style={{ position: "relative", zIndex: 1, textAlign: "center", padding: 24 }}>
        {children}
      </div>
    </section>
  )
}
