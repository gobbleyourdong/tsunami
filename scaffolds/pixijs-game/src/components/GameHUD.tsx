interface GameHUDProps {
  score?: number
  level?: number
  lives?: number
  time?: number
  extra?: Record<string, string | number>
}

/** Overlay HUD — score, lives, level, timer. Positioned over the game canvas. */
export default function GameHUD({ score, level, lives, time, extra }: GameHUDProps) {
  return (
    <div className="game-hud">
      {score !== undefined && <span className="hud-item">Score: <b>{score}</b></span>}
      {level !== undefined && <span className="hud-item">Level: <b>{level}</b></span>}
      {lives !== undefined && <span className="hud-item">Lives: <b>{"❤️".repeat(Math.max(0, lives))}</b></span>}
      {time !== undefined && (
        <span className="hud-item">
          {Math.floor(time / 60)}:{String(Math.floor(time % 60)).padStart(2, "0")}
        </span>
      )}
      {extra && Object.entries(extra).map(([k, v]) => (
        <span key={k} className="hud-item">{k}: <b>{v}</b></span>
      ))}
    </div>
  )
}
