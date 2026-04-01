import { ReactNode } from "react"

interface HeroProps {
  title: string
  subtitle?: string
  cta?: { label: string; onClick?: () => void }
  children?: ReactNode
}

export default function Hero({ title, subtitle, cta, children }: HeroProps) {
  return (
    <section style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      justifyContent: "center", alignItems: "center", textAlign: "center",
      padding: "120px 24px 80px", background: "linear-gradient(135deg, #0a0a1a 0%, #1a1a3a 100%)",
    }}>
      <h1 style={{ fontSize: "clamp(36px, 6vw, 72px)", fontWeight: 800, color: "#fff", lineHeight: 1.1, maxWidth: 800 }}>
        {title}
      </h1>
      {subtitle && (
        <p style={{ fontSize: 20, color: "#888", marginTop: 20, maxWidth: 600, lineHeight: 1.6 }}>
          {subtitle}
        </p>
      )}
      {cta && (
        <button
          onClick={cta.onClick}
          style={{
            marginTop: 32, padding: "14px 36px", fontSize: 16, fontWeight: 600,
            background: "#0ff", color: "#000", border: "none", borderRadius: 8,
            cursor: "pointer",
          }}
        >
          {cta.label}
        </button>
      )}
      {children}
    </section>
  )
}
