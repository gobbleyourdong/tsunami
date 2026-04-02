import { useState } from "react"

interface ColorPickerProps {
  value: string
  onChange: (color: string) => void
  presets?: string[]
}

const DEFAULT_PRESETS = ["#ff4444", "#ff8800", "#ffcc00", "#44cc44", "#00cccc", "#4488ff", "#8844ff", "#ff44aa", "#ffffff", "#888888", "#333333", "#000000"]

/** Color picker with presets and hex input. */
export default function ColorPicker({ value, onChange, presets = DEFAULT_PRESETS }: ColorPickerProps) {
  const [show, setShow] = useState(false)

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <div onClick={() => setShow(!show)} style={{
        width: 36, height: 36, borderRadius: "var(--radius)", border: "2px solid var(--border)",
        background: value, cursor: "pointer",
      }} />
      {show && (
        <div style={{
          position: "absolute", top: 42, left: 0, zIndex: 50,
          background: "var(--bg-card)", border: "1px solid var(--border)",
          borderRadius: "var(--radius)", padding: 12, minWidth: 200,
          boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 4, marginBottom: 8 }}>
            {presets.map(c => (
              <div key={c} onClick={() => { onChange(c); setShow(false) }} style={{
                width: 28, height: 28, borderRadius: 4, background: c, cursor: "pointer",
                border: c === value ? "2px solid var(--accent)" : "1px solid var(--border)",
              }} />
            ))}
          </div>
          <input type="color" value={value} onChange={e => onChange(e.target.value)} style={{ width: "100%", height: 32, cursor: "pointer", border: "none", background: "none" }} />
        </div>
      )}
    </div>
  )
}
