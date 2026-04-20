interface StarRatingProps {
  rating?: number
  value?: number
  max?: number
  count?: number  // alias for max
  size?: number
  color?: string
  onChange?: (rating: number) => void
  onValueChange?: (rating: number) => void
  readOnly?: boolean
  readonly?: boolean
}

export function StarRating({ rating, value, max, count, size = 20, color = "#ffaa00", onChange, onValueChange, readOnly, readonly }: StarRatingProps) {
  const currentRating = rating ?? value ?? 0
  const total = max ?? count ?? 5
  const ro = readOnly || readonly
  const baseHandler = onChange ?? onValueChange
  const handler = ro ? undefined : baseHandler
  return (
    <div style={{ display: "flex", gap: 2 }}>
      {Array.from({ length: total }, (_, i) => (
        <svg
          key={i}
          width={size} height={size} viewBox="0 0 20 20"
          fill={i < currentRating ? color : "var(--border)"}
          style={{ cursor: handler ? "pointer" : "default" }}
          onClick={() => handler?.(i + 1)}
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
    </div>
  )
}

export default StarRating
