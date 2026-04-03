import { useState, useRef, useEffect } from "react"

interface ColorPickerProps {
  value: string
  onChange: (color: string) => void
  presets?: string[]
}

const DEFAULT_PRESETS = [
  "#f06060", "#f09040", "#f0b040", "#34d4b0", "#60a0f0",
  "#8060f0", "#f060a0", "#e2e4e9", "#7a7f8e", "#4a4f5e",
  "#21252f", "#08090d",
]

export default function ColorPicker({ value, onChange, presets = DEFAULT_PRESETS }: ColorPickerProps) {
  const [show, setShow] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setShow(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <div
        onClick={() => setShow(!show)}
        style={{
          width: 36, height: 36,
          borderRadius: 'var(--radius, 10px)',
          border: '2px solid var(--border, rgba(255,255,255,0.06))',
          background: value,
          cursor: 'pointer',
          transition: 'border-color 150ms',
          boxShadow: show ? `0 0 0 3px ${value}30` : 'none',
        }}
      />
      {show && (
        <div style={{
          position: 'absolute', top: 44, left: 0, zIndex: 100,
          background: 'var(--bg-2, #191c24)',
          border: '1px solid var(--border-hover, rgba(255,255,255,0.12))',
          borderRadius: 'var(--radius-lg, 16px)',
          padding: 14, minWidth: 210,
          boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
          animation: 'scale-in 200ms cubic-bezier(0.22, 1.2, 0.36, 1)',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 6, marginBottom: 10 }}>
            {presets.map(c => (
              <div
                key={c}
                onClick={() => { onChange(c); setShow(false) }}
                style={{
                  width: 28, height: 28, borderRadius: 6, background: c, cursor: 'pointer',
                  border: c === value
                    ? '2px solid var(--accent, #34d4b0)'
                    : '1px solid var(--border, rgba(255,255,255,0.06))',
                  transition: 'transform 100ms',
                }}
                onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.15)')}
                onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
              />
            ))}
          </div>
          <input
            type="color"
            value={value}
            onChange={e => onChange(e.target.value)}
            style={{
              width: '100%', height: 32, cursor: 'pointer',
              border: 'none', background: 'none', borderRadius: 4,
            }}
          />
        </div>
      )}
    </div>
  )
}
