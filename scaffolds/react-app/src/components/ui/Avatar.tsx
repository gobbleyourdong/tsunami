interface AvatarProps {
  src?: string
  name?: string
  size?: number
  color?: string
}

export default function Avatar({ src, name = "?", size = 40, color = "var(--accent)" }: AvatarProps) {
  const initials = name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2)

  if (src) {
    return <img src={src} alt={name} style={{ width: size, height: size, borderRadius: "50%", objectFit: "cover" }} />
  }

  return (
    <div style={{
      width: size, height: size, borderRadius: "50%",
      background: `${color}33`, color, display: "flex",
      alignItems: "center", justifyContent: "center",
      fontSize: size * 0.4, fontWeight: 600,
    }}>
      {initials}
    </div>
  )
}
