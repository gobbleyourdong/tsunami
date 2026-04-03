import { useState } from "react"

interface NavbarProps {
  brand: string
  links?: { label: string; href: string }[]
  cta?: { label: string; href: string }
}

export default function Navbar({ brand, links = [], cta }: NavbarProps) {
  const [open, setOpen] = useState(false)

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <a href="#" className="navbar-brand">{brand}</a>

        {/* Desktop nav */}
        <div className="navbar-links">
          {links.map(l => <a key={l.href} href={l.href}>{l.label}</a>)}
          {cta && <a href={cta.href} className="navbar-cta">{cta.label}</a>}
        </div>

        {/* Mobile hamburger */}
        <button
          className="navbar-hamburger"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          <span className={`hamburger-line ${open ? 'open' : ''}`} />
          <span className={`hamburger-line ${open ? 'open' : ''}`} />
          <span className={`hamburger-line ${open ? 'open' : ''}`} />
        </button>
      </div>

      {/* Mobile dropdown */}
      {open && (
        <div className="navbar-mobile" onClick={() => setOpen(false)}>
          {links.map(l => <a key={l.href} href={l.href}>{l.label}</a>)}
          {cta && <a href={cta.href} className="navbar-cta">{cta.label}</a>}
        </div>
      )}
    </nav>
  )
}
