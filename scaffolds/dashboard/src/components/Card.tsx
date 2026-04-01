import { ReactNode } from "react"

interface CardProps {
  title?: string
  children: ReactNode
  style?: React.CSSProperties
}

/** A dashboard card — use for stats, charts, tables, anything. */
export default function Card({ title, children, style }: CardProps) {
  return (
    <div style={{
      background: "#1a1a2e",
      borderRadius: 8,
      border: "1px solid #2a2a4a",
      padding: 20,
      ...style,
    }}>
      {title && (
        <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#888", textTransform: "uppercase", letterSpacing: 1 }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  )
}
