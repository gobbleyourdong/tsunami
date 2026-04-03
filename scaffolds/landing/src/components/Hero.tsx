import { ReactNode } from "react"

interface HeroProps {
  title: string
  subtitle?: string
  cta?: { label: string; onClick?: () => void; href?: string }
  children?: ReactNode
  gradient?: string
}

export default function Hero({ title, subtitle, cta, children, gradient }: HeroProps) {
  return (
    <section className="hero" style={gradient ? { background: gradient } : undefined}>
      <h1 className="hero-title">{title}</h1>
      {subtitle && <p className="hero-subtitle">{subtitle}</p>}
      {cta && (
        cta.href
          ? <a href={cta.href} className="hero-cta">{cta.label}</a>
          : <button onClick={cta.onClick} className="hero-cta">{cta.label}</button>
      )}
      {children}
    </section>
  )
}
