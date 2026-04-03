interface FooterProps {
  brand?: string
  links?: { label: string; href: string }[]
  socials?: { icon: string; href: string }[]
}

export default function Footer({ brand, links = [], socials = [] }: FooterProps) {
  return (
    <footer className="footer">
      <div className="footer-inner">
        {links.length > 0 && (
          <div className="footer-links">
            {links.map(l => <a key={l.href} href={l.href}>{l.label}</a>)}
          </div>
        )}
        {socials.length > 0 && (
          <div className="footer-socials">
            {socials.map(s => <a key={s.href} href={s.href} target="_blank" rel="noopener">{s.icon}</a>)}
          </div>
        )}
        <p className="footer-copy">
          {brand ? `© ${new Date().getFullYear()} ${brand}` : `© ${new Date().getFullYear()}`}
        </p>
      </div>
    </footer>
  )
}
