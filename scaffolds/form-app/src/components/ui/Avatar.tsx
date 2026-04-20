type AvatarSize = number | "xs" | "sm" | "md" | "lg" | "xl" | "2xl"
type AvatarShape = "circle" | "square" | "rounded"

interface AvatarProps {
  src?: string
  name?: string
  fallback?: string  // shadcn alias for `name`
  alt?: string
  size?: AvatarSize
  color?: string
  shape?: AvatarShape
  radius?: number | "none" | "sm" | "md" | "lg" | "full"
  status?: "online" | "offline" | "away" | "busy" | string
  className?: string
}

const SIZE_PX: Record<string, number> = {
  xs: 24, sm: 32, md: 40, lg: 56, xl: 72, "2xl": 96,
}

const STATUS_COLORS: Record<string, string> = {
  online: "var(--success, #34d4b0)",
  offline: "var(--text-dim, #4a4f5e)",
  away: "var(--warning, #f0b040)",
  busy: "var(--danger, #f06060)",
}

function resolveSize(s: AvatarSize): number {
  return typeof s === "number" ? s : SPRESET[s] ?? 40
}
const SPRESET = SIZE_PX

function radiusFor(shape: AvatarShape, size: number, radius?: AvatarProps["radius"]): string | number {
  if (radius != null) {
    if (typeof radius === "number") return radius
    if (radius === "none") return 0
    if (radius === "full") return "50%"
    const map: Record<string, number> = { sm: 4, md: 8, lg: 12 }
    return map[radius] ?? 8
  }
  if (shape === "square") return 0
  if (shape === "rounded") return Math.round(size * 0.2)
  return "50%"
}

export function Avatar({
  src,
  name,
  fallback,
  alt,
  size = 40,
  color = "var(--accent)",
  shape = "circle",
  radius,
  status,
  className,
}: AvatarProps) {
  const px = resolveSize(size)
  const display = fallback ?? name ?? "?"
  const initials = display.split(" ").map(w => w[0]).filter(Boolean).join("").toUpperCase().slice(0, 2) || "?"
  const br = radiusFor(shape, px, radius)

  const wrapper: React.CSSProperties = { position: "relative", display: "inline-block", lineHeight: 0 }
  const dot = status && (
    <span
      aria-hidden
      style={{
        position: "absolute", right: 0, bottom: 0,
        width: Math.max(8, px * 0.22), height: Math.max(8, px * 0.22),
        borderRadius: "50%",
        background: STATUS_COLORS[status] ?? status,
        border: "2px solid var(--bg-0, #08090d)",
      }}
    />
  )

  if (src) {
    return (
      <span className={className} style={wrapper}>
        <img
          src={src}
          alt={alt ?? display}
          style={{ width: px, height: px, borderRadius: br, objectFit: "cover", display: "block" }}
        />
        {dot}
      </span>
    )
  }

  return (
    <span className={className} style={wrapper}>
      <span style={{
        width: px, height: px, borderRadius: br,
        background: `${color}33`, color, display: "inline-flex",
        alignItems: "center", justifyContent: "center",
        fontSize: px * 0.4, fontWeight: 600, lineHeight: 1,
      }}>
        {initials}
      </span>
      {dot}
    </span>
  )
}

export default Avatar
