import { useState, useRef, useCallback } from "react"

interface BeforeAfterProps {
  before: string  // image URL
  after: string   // image URL
  height?: number
}

/** Drag slider to compare two images. */
export function BeforeAfter({ before, after, height = 400 }: BeforeAfterProps) {
  const [pos, setPos] = useState(50)
  const ref = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)

  const update = useCallback((x: number) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    setPos(Math.max(0, Math.min(100, ((x - rect.left) / rect.width) * 100)))
  }, [])

  return (
    <div ref={ref} style={{ position: "relative", height, overflow: "hidden", borderRadius: "var(--radius)", cursor: "ew-resize", userSelect: "none" }}
      onPointerDown={e => { dragging.current = true; (e.target as HTMLElement).setPointerCapture(e.pointerId); update(e.clientX) }}
      onPointerMove={e => dragging.current && update(e.clientX)}
      onPointerUp={() => dragging.current = false}
    >
      <img src={after} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
      <div style={{ position: "absolute", inset: 0, width: `${pos}%`, overflow: "hidden" }}>
        <img src={before} style={{ width: ref.current?.offsetWidth || "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <div style={{ position: "absolute", left: `${pos}%`, top: 0, bottom: 0, width: 3, background: "var(--accent)", transform: "translateX(-50%)" }}>
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: 32, height: 32, borderRadius: "50%", background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "#000", fontWeight: 700 }}>⇔</div>
      </div>
    </div>
  )
}

export default BeforeAfter
