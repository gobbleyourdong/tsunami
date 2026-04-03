interface NavbarProps {
  brand: string
  links?: { label: string; href: string }[]
  cta?: { label: string; href: string }
}

export default function Navbar({ brand, links = [], cta }: NavbarProps) {
  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <a href="#" className="navbar-brand">{brand}</a>
        <div className="navbar-links">
          {links.map(l => <a key={l.href} href={l.href}>{l.label}</a>)}
          {cta && <a href={cta.href} className="navbar-cta">{cta.label}</a>}
        </div>
      </div>
    </nav>
  )
}
