interface FooterProps {
  brand?: string
  links?: { label: string; href: string }[]
}

export default function Footer({ brand = "", links = [] }: FooterProps) {
  return (
    <footer style={{
      padding: "40px 24px", textAlign: "center",
      background: "#0a0a1a", borderTop: "1px solid #222",
      color: "#555", fontSize: 13,
    }}>
      {links.length > 0 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 24, marginBottom: 16 }}>
          {links.map(l => (
            <a key={l.href} href={l.href} style={{ color: "#666", textDecoration: "none" }}>{l.label}</a>
          ))}
        </div>
      )}
      <p>{brand ? `© ${new Date().getFullYear()} ${brand}` : `© ${new Date().getFullYear()}`}</p>
    </footer>
  )
}
