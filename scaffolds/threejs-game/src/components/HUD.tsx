import { ReactNode } from "react"

interface HUDProps {
  children: ReactNode
}

/** 2D overlay on top of the 3D scene. For score, health, menus. */
export default function HUD({ children }: HUDProps) {
  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      padding: "16px",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      fontFamily: "'Courier New', monospace",
      color: "#0ff",
      textShadow: "0 0 8px #0ff",
      fontSize: "18px",
      pointerEvents: "none",
      zIndex: 10,
    }}>
      {children}
    </div>
  )
}
