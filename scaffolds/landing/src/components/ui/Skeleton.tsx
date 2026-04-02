interface SkeletonProps {
  width?: string | number
  height?: string | number
  radius?: number
  style?: React.CSSProperties
}

export default function Skeleton({ width = "100%", height = 20, radius = 6, style }: SkeletonProps) {
  return (
    <div style={{
      width, height, borderRadius: radius,
      background: "linear-gradient(90deg, var(--bg-card) 25%, var(--border) 50%, var(--bg-card) 75%)",
      backgroundSize: "200% 100%",
      animation: "shimmer 1.5s infinite",
      ...style,
    }}>
      <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
    </div>
  )
}
