interface PresenceDotProps {
  connected: boolean
  userCount?: number
}

export default function PresenceDot({ connected, userCount }: PresenceDotProps) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      fontSize: 'var(--text-xs, 0.75rem)',
      fontWeight: 600,
      color: connected ? 'var(--text-muted, #7a7f8e)' : 'var(--text-dim, #4a4f5e)',
    }}>
      <span className={`status-dot ${connected ? "online" : "offline"}`} />
      {connected
        ? userCount ? `${userCount} online` : "Connected"
        : "Disconnected"
      }
    </span>
  )
}
