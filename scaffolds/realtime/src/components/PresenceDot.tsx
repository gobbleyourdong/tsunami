interface PresenceDotProps {
  connected: boolean
  userCount?: number
}

export default function PresenceDot({ connected, userCount }: PresenceDotProps) {
  return (
    <span className="presence">
      <span className={`presence-dot ${connected ? "online" : "offline"}`} />
      {connected
        ? <span>{userCount ? `${userCount} online` : "connected"}</span>
        : <span>disconnected</span>
      }
    </span>
  )
}
