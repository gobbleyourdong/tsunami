import { ReactNode } from "react"

type AlertKind = "info" | "success" | "warning" | "error" | "default" | "destructive"

interface AlertProps {
  type?: AlertKind
  variant?: AlertKind  // shadcn-convention alias for `type`
  title?: string
  children: ReactNode
  onDismiss?: () => void
  className?: string
}

const config = {
  info:    { color: 'var(--accent, #4a9eff)',  bg: 'rgba(74, 158, 255, 0.08)', border: 'rgba(74, 158, 255, 0.2)',  icon: 'ℹ' },
  success: { color: 'var(--success, #34d4b0)', bg: 'rgba(52, 212, 176, 0.08)', border: 'rgba(52, 212, 176, 0.2)',  icon: '✓' },
  warning: { color: 'var(--warning, #f0b040)', bg: 'rgba(240, 176, 64, 0.08)', border: 'rgba(240, 176, 64, 0.2)',  icon: '!' },
  error:   { color: 'var(--danger, #f06060)',  bg: 'rgba(240, 96, 96, 0.08)',  border: 'rgba(240, 96, 96, 0.2)',   icon: '✕' },
}

const ALIAS: Record<AlertKind, keyof typeof config> = {
  info: "info", success: "success", warning: "warning", error: "error",
  default: "info", destructive: "error",
}

export function Alert({ type, variant, title, children, onDismiss, className }: AlertProps) {
  const kind = variant ?? type ?? "info"
  const c = config[ALIAS[kind]]
  return (
    <div className={className} style={{
      display: 'flex', gap: 12, alignItems: 'flex-start',
      padding: '14px 16px',
      borderRadius: 'var(--radius, 10px)',
      border: `1px solid ${c.border}`,
      background: c.bg,
      borderLeft: `3px solid ${c.color}`,
    }}>
      <span style={{
        width: 22, height: 22, borderRadius: '50%',
        background: c.color, color: 'var(--bg-0, #08090d)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700, flexShrink: 0, marginTop: 1,
      }}>
        {c.icon}
      </span>
      <div style={{ flex: 1 }}>
        {title && <div style={{ fontWeight: 700, marginBottom: 2, color: c.color, fontSize: 'var(--text-sm, 0.875rem)' }}>{title}</div>}
        <div style={{ fontSize: 'var(--text-sm, 0.875rem)', color: 'var(--text, #e2e4e9)', lineHeight: 1.6 }}>{children}</div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{
            background: 'none', border: 'none', color: 'var(--text-dim, #4a4f5e)',
            cursor: 'pointer', fontSize: 16, padding: '2px 4px', lineHeight: 1,
          }}
        >
          ×
        </button>
      )}
    </div>
  )
}

export default Alert
