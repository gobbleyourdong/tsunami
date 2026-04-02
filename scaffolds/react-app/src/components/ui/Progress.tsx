interface ProgressProps {
  value: number  // 0-100
  color?: string
  height?: number
  showLabel?: boolean
}

export default function Progress({ value, color = "var(--accent)", height = 8, showLabel = false }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <div style={{ width: "100%" }}>
      <div style={{ background: "var(--bg-card)", borderRadius: height, height, overflow: "hidden", border: "1px solid var(--border)" }}>
        <div style={{ width: `${clamped}%`, height: "100%", background: color, borderRadius: height, transition: "width 0.3s ease" }} />
      </div>
      {showLabel && <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4, textAlign: "right" }}>{clamped}%</div>}
    </div>
  )
}
