interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label?: string
}

export default function Switch({ checked, onChange, label }: SwitchProps) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
      <div onClick={() => onChange(!checked)} style={{
        width: 44, height: 24, borderRadius: 12, padding: 2,
        background: checked ? "var(--accent)" : "var(--border)",
        transition: "background 0.2s", cursor: "pointer",
      }}>
        <div style={{
          width: 20, height: 20, borderRadius: "50%",
          background: "#fff", transition: "transform 0.2s",
          transform: checked ? "translateX(20px)" : "translateX(0)",
        }} />
      </div>
      {label && <span style={{ fontSize: 14 }}>{label}</span>}
    </label>
  )
}
