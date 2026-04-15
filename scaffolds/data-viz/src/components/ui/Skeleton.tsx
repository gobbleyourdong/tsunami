interface SkeletonProps {
  width?: string | number
  height?: string | number
  radius?: number
  circle?: boolean
  className?: string
  style?: React.CSSProperties
}

export default function Skeleton({ width = "100%", height = 20, radius = 6, circle, className = "", style }: SkeletonProps) {
  const size = circle ? (typeof height === 'number' ? height : 40) : undefined

  return (
    <div
      className={`skeleton ${className}`.trim()}
      style={{
        width: circle ? size : width,
        height: circle ? size : height,
        borderRadius: circle ? '50%' : radius,
        ...style,
      }}
    />
  )
}
