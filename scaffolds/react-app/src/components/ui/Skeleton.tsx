import React from "react"

type SkeletonVariant = "rect" | "rectangle" | "rectangular" | "text" | "circle" | "circular"
type SkeletonAnimation = "pulse" | "wave" | "none" | false

interface SkeletonProps {
  width?: string | number
  height?: string | number
  size?: number  // alias for width+height (square)
  radius?: number
  circle?: boolean
  variant?: SkeletonVariant
  lines?: number
  animation?: SkeletonAnimation
  className?: string
  style?: React.CSSProperties
}

function isCircle(variant: SkeletonVariant | undefined, circle: boolean | undefined): boolean {
  return circle === true || variant === "circle" || variant === "circular"
}

function isText(variant: SkeletonVariant | undefined): boolean {
  return variant === "text"
}

const ANIM_CLASS: Record<string, string> = {
  pulse: "skeleton-pulse",
  wave: "skeleton-wave",
}

export function Skeleton({
  width = "100%",
  height = 20,
  size,
  radius = 6,
  circle,
  variant,
  lines,
  animation = "pulse",
  className = "",
  style,
}: SkeletonProps) {
  const isCirc = isCircle(variant, circle)
  const dim = size != null
    ? { width: size, height: size }
    : isCirc
    ? { width: typeof height === "number" ? height : 40, height: typeof height === "number" ? height : 40 }
    : { width, height }

  const animCls = animation && animation !== "none" ? (ANIM_CLASS[animation as string] ?? "") : ""
  const baseCls = `skeleton ${animCls} ${className}`.trim()

  if (isText(variant) && lines && lines > 1) {
    return (
      <div className={className} style={style}>
        {Array.from({ length: lines }, (_, i) => (
          <div
            key={i}
            className={`skeleton ${animCls}`.trim()}
            style={{
              width: i === lines - 1 ? "70%" : "100%",
              height: typeof height === "number" ? height : 14,
              borderRadius: radius,
              marginBottom: i < lines - 1 ? 8 : 0,
            }}
          />
        ))}
      </div>
    )
  }

  return (
    <div
      className={baseCls}
      style={{
        ...dim,
        borderRadius: isCirc ? '50%' : radius,
        ...style,
      }}
    />
  )
}

export default Skeleton
