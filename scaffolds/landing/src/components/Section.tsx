import { ReactNode } from "react"

interface SectionProps {
  id?: string
  title?: string
  subtitle?: string
  children: ReactNode
  dark?: boolean
}

export default function Section({ id, title, subtitle, children, dark = false }: SectionProps) {
  return (
    <section id={id} style={{
      padding: "80px 24px",
      background: dark ? "#0f0f1a" : "#111128",
    }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        {title && <h2 style={{ fontSize: 36, fontWeight: 700, color: "#fff", marginBottom: 8 }}>{title}</h2>}
        {subtitle && <p style={{ fontSize: 16, color: "#888", marginBottom: 40 }}>{subtitle}</p>}
        {children}
      </div>
    </section>
  )
}
