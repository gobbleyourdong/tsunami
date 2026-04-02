import { useState, useEffect } from "react"

interface SlideshowProps {
  images: string[]
  interval?: number  // ms between slides
  height?: number
  showDots?: boolean
  showArrows?: boolean
}

/** Auto-advancing image slideshow with dots and arrows. */
export default function Slideshow({ images, interval = 4000, height = 400, showDots = true, showArrows = true }: SlideshowProps) {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    if (images.length <= 1) return
    const id = setInterval(() => setCurrent(i => (i + 1) % images.length), interval)
    return () => clearInterval(id)
  }, [images.length, interval])

  const go = (dir: number) => setCurrent(i => (i + dir + images.length) % images.length)

  return (
    <div style={{ position: "relative", height, overflow: "hidden", borderRadius: "var(--radius)", background: "#000" }}>
      {images.map((img, i) => (
        <img key={i} src={img} style={{
          position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover",
          opacity: i === current ? 1 : 0, transition: "opacity 0.5s ease",
        }} />
      ))}
      {showArrows && images.length > 1 && <>
        <button onClick={() => go(-1)} style={{ position: "absolute", left: 8, top: "50%", transform: "translateY(-50%)", background: "rgba(0,0,0,0.5)", border: "none", color: "#fff", width: 36, height: 36, borderRadius: "50%", cursor: "pointer", fontSize: 18 }}>‹</button>
        <button onClick={() => go(1)} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "rgba(0,0,0,0.5)", border: "none", color: "#fff", width: 36, height: 36, borderRadius: "50%", cursor: "pointer", fontSize: 18 }}>›</button>
      </>}
      {showDots && images.length > 1 && (
        <div style={{ position: "absolute", bottom: 12, left: "50%", transform: "translateX(-50%)", display: "flex", gap: 6 }}>
          {images.map((_, i) => (
            <div key={i} onClick={() => setCurrent(i)} style={{
              width: 8, height: 8, borderRadius: "50%", cursor: "pointer",
              background: i === current ? "var(--accent)" : "rgba(255,255,255,0.4)",
            }} />
          ))}
        </div>
      )}
    </div>
  )
}
