type ProgressSize = "xs" | "sm" | "md" | "lg" | "xl"

interface ProgressProps {
  value?: number
  max?: number
  color?: string
  height?: number
  size?: ProgressSize
  showLabel?: boolean
  showValue?: boolean  // alias for showLabel
  variant?: "default" | "striped" | "gradient"
  indeterminate?: boolean
  className?: string
}

const SIZE_PX: Record<ProgressSize, number> = {
  xs: 3, sm: 4, md: 6, lg: 10, xl: 14,
}

const COLOR_PRESETS: Record<string, string> = {
  primary: "var(--accent, #4a9eff)",
  default: "var(--accent, #4a9eff)",
  success: "var(--success, #34d4b0)",
  warning: "var(--warning, #f0b040)",
  danger: "var(--danger, #f06060)",
  destructive: "var(--danger, #f06060)",
}

export function Progress({
  value = 0,
  max = 100,
  color,
  height,
  size,
  showLabel = false,
  showValue = false,
  variant = "default",
  indeterminate = false,
  className,
}: ProgressProps) {
  const h = height ?? (size ? SIZE_PX[size] : 6)
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0
  const bg = color ? (COLOR_PRESETS[color] ?? color) : 'var(--accent, #4a9eff)'
  const showNumber = showLabel || showValue

  return (
    <div className={className} style={{ width: '100%' }}>
      <div style={{
        background: 'var(--bg-2, #191c24)',
        borderRadius: h,
        height: h,
        overflow: 'hidden',
        position: 'relative',
      }}>
        {indeterminate ? (
          <>
            <style>{`@keyframes ind-progress { 0% { left: -40%; } 100% { left: 100%; } }`}</style>
            <div style={{
              position: 'absolute', top: 0, bottom: 0, width: '40%',
              background: `linear-gradient(90deg, transparent, ${bg}, transparent)`,
              animation: 'ind-progress 1.2s ease-in-out infinite',
            }} />
          </>
        ) : (
          <div style={{
            width: `${pct}%`,
            height: '100%',
            background: variant === "striped"
              ? `repeating-linear-gradient(45deg, ${bg}, ${bg} 10px, transparent 10px, transparent 20px)`
              : variant === "gradient"
              ? `linear-gradient(90deg, ${bg}, ${bg}80)`
              : `linear-gradient(90deg, ${bg}, ${bg}dd)`,
            borderRadius: h,
            transition: 'width 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
            boxShadow: pct > 0 ? `0 0 8px ${bg}40` : 'none',
          }} />
        )}
      </div>
      {showNumber && !indeterminate && (
        <div style={{
          fontSize: 'var(--text-xs, 0.75rem)',
          color: 'var(--text-muted, #7a7f8e)',
          marginTop: 4,
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {Math.round(pct)}%
        </div>
      )}
    </div>
  )
}

export default Progress
