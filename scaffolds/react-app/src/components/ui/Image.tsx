import React from "react"

interface ImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  alt?: string
  radius?: number | string  // border-radius shortcut
  fit?: "cover" | "contain" | "fill" | "none" | "scale-down"
  rounded?: boolean | "sm" | "md" | "lg" | "full"
}

const ROUNDED: Record<string, number | string> = {
  sm: 4, md: 8, lg: 12, full: "50%",
}

export function Image({ alt = "", className = "", style, radius, fit, rounded, ...props }: ImageProps) {
  const br =
    radius != null
      ? radius
      : rounded === true
      ? 8
      : typeof rounded === "string"
      ? ROUNDED[rounded] ?? 8
      : undefined
  return (
    <img
      alt={alt}
      className={className}
      style={{
        ...(br != null ? { borderRadius: br } : {}),
        ...(fit ? { objectFit: fit } : {}),
        ...style,
      }}
      {...props}
    />
  )
}

export default Image
