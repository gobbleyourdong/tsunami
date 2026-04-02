interface BadgeProps {
  children: React.ReactNode
  color?: string
}

/** Small label badge — use for status, tags, counts. */
export default function Badge({ children, color = "var(--accent)" }: BadgeProps) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 10px",
      borderRadius: 12,
      fontSize: 12,
      fontWeight: 600,
      background: `${color}22`,
      color: color,
      border: `1px solid ${color}44`,
    }}>
      {children}
    </span>
  )
}
