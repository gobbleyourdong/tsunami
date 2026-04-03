interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label?: string
  size?: "sm" | "md"
}

export default function Switch({ checked, onChange, label, size = "md" }: SwitchProps) {
  const w = size === "sm" ? 36 : 44
  const h = size === "sm" ? 20 : 24
  const thumb = size === "sm" ? 16 : 20

  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', userSelect: 'none' }}>
      <div
        role="switch"
        aria-checked={checked}
        tabIndex={0}
        onClick={() => onChange(!checked)}
        onKeyDown={e => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); onChange(!checked) } }}
        style={{
          width: w, height: h, borderRadius: h, padding: 2,
          background: checked ? 'var(--accent, #34d4b0)' : 'var(--bg-4, #2a2f3b)',
          transition: 'background 200ms cubic-bezier(0.16, 1, 0.3, 1)',
          cursor: 'pointer',
          boxShadow: checked ? '0 0 8px rgba(52, 212, 176, 0.25)' : 'none',
          flexShrink: 0,
        }}
      >
        <div style={{
          width: thumb, height: thumb, borderRadius: '50%',
          background: '#fff',
          transition: 'transform 200ms cubic-bezier(0.16, 1, 0.3, 1)',
          transform: checked ? `translateX(${w - thumb - 4}px)` : 'translateX(0)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
        }} />
      </div>
      {label && <span style={{ fontSize: 'var(--text-sm, 0.875rem)', color: 'var(--text, #e2e4e9)' }}>{label}</span>}
    </label>
  )
}
