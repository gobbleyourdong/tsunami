interface ProgressProps {
  value: number
  color?: string
  height?: number
  showLabel?: boolean
  variant?: "default" | "striped"
  className?: string
}

export default function Progress({ value, color, height = 6, showLabel = false, variant = "default", className }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value))
  const bg = color || 'var(--accent, #4a9eff)'

  return (
    <div className={className} style={{ width: '100%' }}>
      <div style={{
        background: 'var(--bg-2, #191c24)',
        borderRadius: height,
        height,
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${clamped}%`,
          height: '100%',
          background: variant === "striped"
            ? `repeating-linear-gradient(45deg, ${bg}, ${bg} 10px, transparent 10px, transparent 20px)`
            : `linear-gradient(90deg, ${bg}, ${bg}dd)`,
          borderRadius: height,
          transition: 'width 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
          boxShadow: clamped > 0 ? `0 0 8px ${bg}40` : 'none',
        }} />
      </div>
      {showLabel && (
        <div style={{
          fontSize: 'var(--text-xs, 0.75rem)',
          color: 'var(--text-muted, #7a7f8e)',
          marginTop: 4,
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {clamped}%
        </div>
      )}
    </div>
  )
}
