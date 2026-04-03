interface Testimonial {
  quote: string
  name: string
  role?: string
  avatar?: string
}

interface TestimonialsProps {
  testimonials: Testimonial[]
  title?: string
  subtitle?: string
}

export default function Testimonials({ testimonials, title, subtitle }: TestimonialsProps) {
  return (
    <div>
      {title && <h2 className="section-title">{title}</h2>}
      {subtitle && <p className="section-subtitle">{subtitle}</p>}
      <div className="feature-grid grid-3">
        {testimonials.map((t, i) => (
          <div key={i} className="glass" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <p style={{ fontSize: 'var(--text-md)', lineHeight: 1.7, color: 'var(--text)', flex: 1 }}>
              "{t.quote}"
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div className="avatar">
                {t.avatar
                  ? <img src={t.avatar} alt={t.name} />
                  : t.name.charAt(0).toUpperCase()
                }
              </div>
              <div>
                <div style={{ fontWeight: 700, color: '#fff', fontSize: 'var(--text-sm)' }}>{t.name}</div>
                {t.role && <div style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>{t.role}</div>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
