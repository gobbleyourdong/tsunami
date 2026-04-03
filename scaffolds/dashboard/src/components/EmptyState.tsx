interface EmptyStateProps {
  icon?: string
  title: string
  description?: string
  action?: { label: string; onClick: () => void }
}

/** Placeholder for empty lists, search results, etc. */
export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '64px 24px', textAlign: 'center',
    }}>
      {icon && (
        <div style={{
          fontSize: 48, marginBottom: 16, opacity: 0.3,
          filter: 'grayscale(0.5)',
        }}>
          {icon}
        </div>
      )}
      <h3 style={{
        fontSize: 'var(--text-lg)', fontWeight: 700, color: '#fff',
        marginBottom: 8,
      }}>
        {title}
      </h3>
      {description && (
        <p style={{
          fontSize: 'var(--text-sm)', color: 'var(--text-muted)',
          maxWidth: 360, lineHeight: 1.6,
        }}>
          {description}
        </p>
      )}
      {action && (
        <button className="primary" onClick={action.onClick} style={{ marginTop: 20 }}>
          {action.label}
        </button>
      )}
    </div>
  )
}
