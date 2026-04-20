import { useState, useRef, useCallback, ReactNode } from "react"

interface BeforeAfterProps {
  before?: string  // image URL
  after?: string   // image URL
  beforeImage?: string  // alias drones reach for
  afterImage?: string
  labelBefore?: string
  labelAfter?: string
  height?: number
  className?: string
  children?: ReactNode
}

/** Drag slider to compare two images. */
export function BeforeAfter({ before, after, beforeImage, afterImage, labelBefore, labelAfter, height = 400, className, children }: BeforeAfterProps) {
  const beforeSrc = before ?? beforeImage ?? ""
  const afterSrc = after ?? afterImage ?? ""
  const [pos, setPos] = useState(50)
  const ref = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)

  const update = useCallback((x: number) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    setPos(Math.max(0, Math.min(100, ((x - rect.left) / rect.width) * 100)))
  }, [])

  return (
    <div ref={ref} className={className} style={{ position: "relative", height, overflow: "hidden", borderRadius: "var(--radius)", cursor: "ew-resize", userSelect: "none" }}
      onPointerDown={e => { dragging.current = true; (e.target as HTMLElement).setPointerCapture(e.pointerId); update(e.clientX) }}
      onPointerMove={e => dragging.current && update(e.clientX)}
      onPointerUp={() => dragging.current = false}
    >
      <img src={afterSrc} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
      <div style={{ position: "absolute", inset: 0, width: `${pos}%`, overflow: "hidden" }}>
        <img src={beforeSrc} style={{ width: ref.current?.offsetWidth || "100%", height: "100%", objectFit: "cover" }} />
      </div>
      {labelBefore && <span style={{ position: "absolute", top: 12, left: 12, padding: "4px 10px", background: "rgba(0,0,0,0.6)", color: "#fff", fontSize: 12, borderRadius: 4 }}>{labelBefore}</span>}
      {labelAfter && <span style={{ position: "absolute", top: 12, right: 12, padding: "4px 10px", background: "rgba(0,0,0,0.6)", color: "#fff", fontSize: 12, borderRadius: 4 }}>{labelAfter}</span>}
      <div style={{ position: "absolute", left: `${pos}%`, top: 0, bottom: 0, width: 3, background: "var(--accent)", transform: "translateX(-50%)" }}>
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: 32, height: 32, borderRadius: "50%", background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "#000", fontWeight: 700 }}>⇔</div>
      </div>
      {children}
    </div>
  )
}

export default BeforeAfter
