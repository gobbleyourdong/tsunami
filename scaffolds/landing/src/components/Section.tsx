import { ReactNode } from "react"

interface SectionProps {
  id?: string
  title?: string
  subtitle?: string
  children: ReactNode
  dark?: boolean
  centered?: boolean
}

export default function Section({ id, title, subtitle, children, dark, centered }: SectionProps) {
  return (
    <section id={id} className={`section ${dark ? "section-dark" : ""}`}>
      <div className="section-inner">
        {title && <h2 className={`section-title ${centered ? "text-center" : ""}`}>{title}</h2>}
        {subtitle && <p className={`section-subtitle ${centered ? "text-center" : ""}`}>{subtitle}</p>}
        {children}
      </div>
    </section>
  )
}
