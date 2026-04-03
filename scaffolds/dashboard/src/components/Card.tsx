import { ReactNode } from "react"

interface CardProps {
  title?: string
  children: ReactNode
  style?: React.CSSProperties
}

export default function Card({ title, children, style }: CardProps) {
  return (
    <div className="card" style={style}>
      {title && (
        <h3 style={{
          margin: '0 0 14px',
          fontSize: 'var(--text-xs, 0.75rem)',
          fontWeight: 600,
          color: 'var(--text-muted, #7a7f8e)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  )
}
