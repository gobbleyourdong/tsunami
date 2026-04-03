interface CTASectionProps {
  title: string
  subtitle?: string
  buttonLabel: string
  buttonHref?: string
  onButtonClick?: () => void
}

export default function CTASection({ title, subtitle, buttonLabel, buttonHref, onButtonClick }: CTASectionProps) {
  return (
    <div className="glass" style={{
      textAlign: 'center',
      padding: '64px 32px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Ambient glow behind */}
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 400,
        height: 400,
        background: 'radial-gradient(circle, rgba(74,158,255,0.08) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <h2 style={{
        fontSize: 'var(--text-2xl)',
        fontWeight: 800,
        color: '#fff',
        letterSpacing: '-0.03em',
        marginBottom: 12,
        position: 'relative',
      }}>
        {title}
      </h2>

      {subtitle && (
        <p style={{
          fontSize: 'var(--text-md)',
          color: 'var(--text-muted)',
          maxWidth: 480,
          margin: '0 auto 32px',
          lineHeight: 1.7,
          position: 'relative',
        }}>
          {subtitle}
        </p>
      )}

      {buttonHref ? (
        <a href={buttonHref} className="hero-cta" style={{ position: 'relative' }}>
          {buttonLabel}
        </a>
      ) : (
        <button
          onClick={onButtonClick}
          className="primary"
          style={{
            padding: '16px 40px',
            fontSize: 'var(--text-md)',
            fontWeight: 700,
            borderRadius: 'var(--radius-lg)',
            position: 'relative',
          }}
        >
          {buttonLabel}
        </button>
      )}
    </div>
  )
}
