import React from "react"

interface MetricCardProps {
  label: string
  value: React.ReactNode
  delta?: number
  deltaLabel?: string
  prefix?: string
  suffix?: string
  hint?: string
  icon?: React.ReactNode
  invertDelta?: boolean
  className?: string
  style?: React.CSSProperties
}

function formatDelta(n: number): string {
  const sign = n > 0 ? "+" : ""
  if (Math.abs(n) >= 100) return `${sign}${Math.round(n)}`
  return `${sign}${n.toFixed(1)}`
}

export default function MetricCard({
  label,
  value,
  delta,
  deltaLabel,
  prefix = "",
  suffix = "",
  hint,
  icon,
  invertDelta = false,
  className = "",
  style,
}: MetricCardProps) {
  const hasDelta = typeof delta === "number" && !Number.isNaN(delta)
  const rising = hasDelta && delta! > 0
  const falling = hasDelta && delta! < 0
  const good = invertDelta ? falling : rising
  const bad = invertDelta ? rising : falling
  const arrow = rising ? "↑" : falling ? "↓" : "→"
  const color = good
    ? "var(--success)"
    : bad
    ? "var(--danger)"
    : "var(--text-muted)"
  const bg = good
    ? "rgba(52, 212, 176, 0.12)"
    : bad
    ? "rgba(240, 96, 96, 0.12)"
    : "var(--bg-3)"

  return (
    <div
      className={className}
      style={{
        background: "var(--bg-1)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        transition: "all var(--duration-normal) var(--ease-out-expo)",
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <span
          style={{
            fontSize: "var(--text-xs)",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          {label}
        </span>
        {icon && <span style={{ color: "var(--text-muted)", display: "inline-flex" }}>{icon}</span>}
      </div>

      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "var(--text-2xl)",
          fontWeight: 700,
          color: "#fff",
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
        }}
      >
        {prefix}
        {value}
        {suffix}
      </div>

      {(hasDelta || hint) && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {hasDelta && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "2px 8px",
                borderRadius: 100,
                background: bg,
                color,
                fontSize: "var(--text-xs)",
                fontWeight: 600,
                fontFamily: "var(--font-mono)",
              }}
            >
              <span aria-hidden>{arrow}</span>
              {formatDelta(delta!)}
              {suffix === "%" ? "" : ""}
              {deltaLabel && (
                <span style={{ color: "var(--text-muted)", fontWeight: 500, marginLeft: 4 }}>
                  {deltaLabel}
                </span>
              )}
            </span>
          )}
          {hint && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--text-dim)" }}>{hint}</span>
          )}
        </div>
      )}
    </div>
  )
}
