interface NavbarProps {
  brand: string
  links?: { label: string; href: string }[]
}

export default function Navbar({ brand, links = [] }: NavbarProps) {
  return (
    <nav style={{
      position: "fixed", top: 0, width: "100%", zIndex: 50,
      background: "rgba(10,10,26,0.9)", backdropFilter: "blur(8px)",
      borderBottom: "1px solid #222", padding: "12px 0",
    }}>
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <a href="#" style={{ color: "#fff", fontSize: 20, fontWeight: 700, textDecoration: "none" }}>{brand}</a>
        <div style={{ display: "flex", gap: 24 }}>
          {links.map(l => (
            <a key={l.href} href={l.href} style={{ color: "#aaa", textDecoration: "none", fontSize: 14 }}>{l.label}</a>
          ))}
        </div>
      </div>
    </nav>
  )
}
