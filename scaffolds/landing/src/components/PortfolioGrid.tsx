import { useState } from "react"

interface PortfolioItem {
  title: string
  description: string
  image?: string
  tags?: string[]
  link?: string
}

interface PortfolioGridProps {
  items: PortfolioItem[]
  columns?: number
}

/** Interactive portfolio grid with hover effects and tag filtering. */
export default function PortfolioGrid({ items, columns = 3 }: PortfolioGridProps) {
  const [activeTag, setActiveTag] = useState<string | null>(null)
  const allTags = [...new Set(items.flatMap(i => i.tags || []))]
  const filtered = activeTag ? items.filter(i => i.tags?.includes(activeTag)) : items

  return (
    <div>
      {allTags.length > 0 && (
        <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
          <button onClick={() => setActiveTag(null)} style={{
            padding: "6px 14px", borderRadius: 20, border: "1px solid var(--border)",
            background: !activeTag ? "var(--accent)" : "transparent",
            color: !activeTag ? "#000" : "var(--text)", cursor: "pointer", fontSize: 12,
          }}>All</button>
          {allTags.map(tag => (
            <button key={tag} onClick={() => setActiveTag(tag)} style={{
              padding: "6px 14px", borderRadius: 20, border: "1px solid var(--border)",
              background: activeTag === tag ? "var(--accent)" : "transparent",
              color: activeTag === tag ? "#000" : "var(--text)", cursor: "pointer", fontSize: 12,
            }}>{tag}</button>
          ))}
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: 16 }}>
        {filtered.map((item, i) => (
          <a key={i} href={item.link || "#"} style={{ textDecoration: "none", color: "inherit" }}>
            <div style={{
              background: "var(--bg-card, #1a1a2e)", borderRadius: 12,
              overflow: "hidden", border: "1px solid var(--border, #2a2a4a)",
              transition: "transform 0.2s, box-shadow 0.2s", cursor: "pointer",
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = "translateY(-4px)"; e.currentTarget.style.boxShadow = "0 8px 24px rgba(0,0,0,0.3)" }}
            onMouseLeave={e => { e.currentTarget.style.transform = ""; e.currentTarget.style.boxShadow = "" }}
            >
              {item.image && <div style={{ height: 180, backgroundImage: `url(${item.image})`, backgroundSize: "cover", backgroundPosition: "center" }} />}
              <div style={{ padding: 16 }}>
                <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{item.title}</h3>
                <p style={{ fontSize: 13, color: "var(--text-muted, #888)", lineHeight: 1.5 }}>{item.description}</p>
                {item.tags && (
                  <div style={{ display: "flex", gap: 4, marginTop: 8, flexWrap: "wrap" }}>
                    {item.tags.map(t => <span key={t} style={{ fontSize: 11, padding: "2px 8px", borderRadius: 10, background: "rgba(0,204,204,0.15)", color: "var(--accent, #0cc)" }}>{t}</span>)}
                  </div>
                )}
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
