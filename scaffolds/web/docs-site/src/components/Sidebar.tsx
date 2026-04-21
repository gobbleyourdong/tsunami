import { nav } from "../data/docs"

type Props = { current: string; onSelect: (slug: string) => void }

export default function Sidebar({ current, onSelect }: Props) {
  return (
    <nav className="sidebar">
      <div className="brand">Docs</div>
      {nav.sections.map(section => (
        <div key={section.title}>
          <div className="section-title">{section.title}</div>
          {section.pages.map(p => (
            <a
              key={p.slug}
              href={`#${p.slug}`}
              className={p.slug === current ? "active" : ""}
              onClick={e => { e.preventDefault(); onSelect(p.slug) }}
            >
              {p.title}
            </a>
          ))}
        </div>
      ))}
    </nav>
  )
}
