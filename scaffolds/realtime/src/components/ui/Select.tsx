interface SelectProps {
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
  label?: string
}

export default function Select({ value, onChange, options, placeholder, label }: SelectProps) {
  return (
    <div>
      {label && (
        <label style={{
          display: 'block',
          fontSize: 'var(--text-xs, 0.75rem)',
          fontWeight: 600,
          color: 'var(--text-muted, #7a7f8e)',
          marginBottom: 6,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}>
          {label}
        </label>
      )}
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          background: 'var(--bg-1, #111318)',
          color: 'var(--text, #e2e4e9)',
          border: '1px solid var(--border, rgba(255,255,255,0.06))',
          borderRadius: 'var(--radius, 10px)',
          padding: '11px 36px 11px 14px',
          fontSize: 'var(--text-sm, 0.875rem)',
          fontFamily: 'inherit',
          width: '100%',
          outline: 'none',
          cursor: 'pointer',
          appearance: 'none',
          boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.2)',
          transition: 'border-color 200ms, box-shadow 200ms',
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%237a7f8e' d='M6 8L1 3h10z'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'right 14px center',
        }}
        onFocus={e => {
          e.currentTarget.style.borderColor = 'var(--accent, #4a9eff)'
          e.currentTarget.style.boxShadow = 'inset 0 2px 4px rgba(0,0,0,0.2), 0 0 0 3px rgba(74, 158, 255, 0.12)'
        }}
        onBlur={e => {
          e.currentTarget.style.borderColor = 'var(--border, rgba(255,255,255,0.06))'
          e.currentTarget.style.boxShadow = 'inset 0 2px 4px rgba(0,0,0,0.2)'
        }}
      >
        {placeholder && <option value="" disabled>{placeholder}</option>}
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}
