type SwitchSize = "sm" | "md" | "lg"
type SwitchColor = "default" | "primary" | "success" | "warning" | "danger" | string

interface SwitchProps {
  checked?: boolean
  value?: boolean
  defaultChecked?: boolean
  onChange?: (checked: boolean) => void
  onCheckedChange?: (checked: boolean) => void
  onValueChange?: (checked: boolean) => void
  label?: string
  size?: SwitchSize
  disabled?: boolean
  color?: SwitchColor
  className?: string
}

const COLOR_VAR: Record<string, string> = {
  default: "var(--accent, #4a9eff)",
  primary: "var(--accent, #4a9eff)",
  success: "var(--success, #34d4b0)",
  warning: "var(--warning, #f0b040)",
  danger: "var(--danger, #f06060)",
}

const DIM: Record<SwitchSize, { w: number; h: number; thumb: number }> = {
  sm: { w: 36, h: 20, thumb: 16 },
  md: { w: 44, h: 24, thumb: 20 },
  lg: { w: 56, h: 30, thumb: 26 },
}

export function Switch({ checked, value, defaultChecked, onChange, onCheckedChange, onValueChange, label, size = "md", disabled = false, color = "primary", className }: SwitchProps) {
  const isChecked = checked ?? value ?? defaultChecked ?? false
  const handler = onChange ?? onCheckedChange ?? onValueChange ?? (() => {})
  const onColor = COLOR_VAR[color] ?? color
  const { w, h, thumb } = DIM[size]

  return (
    <label className={className} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: disabled ? 'not-allowed' : 'pointer', userSelect: 'none', opacity: disabled ? 0.5 : 1 }}>
      <div
        role="switch"
        aria-checked={isChecked}
        aria-disabled={disabled}
        tabIndex={disabled ? -1 : 0}
        onClick={() => !disabled && handler(!isChecked)}
        onKeyDown={e => { if (!disabled && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); handler(!isChecked) } }}
        style={{
          width: w, height: h, borderRadius: h, padding: 2,
          background: isChecked ? onColor : 'var(--bg-4, #2a2f3b)',
          transition: 'background 200ms cubic-bezier(0.16, 1, 0.3, 1)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          boxShadow: isChecked ? `0 0 8px ${onColor}40` : 'none',
          flexShrink: 0,
        }}
      >
        <div style={{
          width: thumb, height: thumb, borderRadius: '50%',
          background: '#fff',
          transition: 'transform 200ms cubic-bezier(0.16, 1, 0.3, 1)',
          transform: isChecked ? `translateX(${w - thumb - 4}px)` : 'translateX(0)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
        }} />
      </div>
      {label && <span style={{ fontSize: 'var(--text-sm, 0.875rem)', color: 'var(--text, #e2e4e9)' }}>{label}</span>}
    </label>
  )
}

export default Switch
