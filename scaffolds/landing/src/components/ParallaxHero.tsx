import { useEffect, useState, ReactNode } from "react"

interface ParallaxHeroProps {
  bgImage?: string
  height?: string
  children: ReactNode
  speed?: number
  overlay?: boolean
}

export default function ParallaxHero({
  bgImage,
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
    <section className="hero" style={{ minHeight: height }}>
      {bgImage && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: `url(${bgImage})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            transform: `translateY(${offset}px)`,
            willChange: 'transform',
          }}
        />
      )}
      {overlay && (
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(8,9,13,0.6)', zIndex: 0 }} />
      )}
      <div style={{ position: 'relative', zIndex: 1, textAlign: 'center', padding: 24 }}>
        {children}
      </div>
    </section>
  )
}
