import { ReactNode } from "react"

interface HUDProps {
  children: ReactNode
  position?: "top" | "bottom"
}

/** 2D overlay on top of the 3D scene. For score, health, menus.
 *  pointer-events:none so clicks pass through to the 3D canvas. */
export default function HUD({ children, position = "top" }: HUDProps) {
  return (
    <div className={`hud-3d ${position === "bottom" ? "hud-bottom" : ""}`}>
      {children}
    </div>
  )
}

/** Stat display for the HUD — label + value with neon glow */
export function HUDStat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <span className="hud-stat" style={color ? { color } : undefined}>
      <span className="hud-label">{label}</span>
      <span className="hud-value">{value}</span>
    </span>
  )
}
