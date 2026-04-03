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

export default function PortfolioGrid({ items, columns = 3 }: PortfolioGridProps) {
  const [activeTag, setActiveTag] = useState<string | null>(null)
  const allTags = [...new Set(items.flatMap(i => i.tags || []))]
  const filtered = activeTag ? items.filter(i => i.tags?.includes(activeTag)) : items

  return (
    <div>
      {allTags.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
          <button
            className={!activeTag ? 'primary' : 'ghost'}
            onClick={() => setActiveTag(null)}
            style={{ padding: '6px 16px', borderRadius: 100, fontSize: 'var(--text-xs, 0.75rem)' }}
          >
            All
          </button>
          {allTags.map(tag => (
            <button
              key={tag}
              className={activeTag === tag ? 'primary' : 'ghost'}
              onClick={() => setActiveTag(tag)}
              style={{ padding: '6px 16px', borderRadius: 100, fontSize: 'var(--text-xs, 0.75rem)' }}
            >
              {tag}
            </button>
          ))}
        </div>
      )}
      <div className="gallery-grid" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
        {filtered.map((item, i) => (
          <a key={i} href={item.link || '#'} style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="gallery-item" style={{ aspectRatio: 'auto' }}>
              {item.image && (
                <div style={{
                  height: 200,
                  backgroundImage: `url(${item.image})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                }} />
              )}
              <div style={{ padding: 18 }}>
                <h3 style={{
                  fontSize: 'var(--text-md, 1rem)',
                  fontWeight: 700, color: '#fff', marginBottom: 6,
                }}>
                  {item.title}
                </h3>
                <p style={{
                  fontSize: 'var(--text-sm, 0.875rem)',
                  color: 'var(--text-muted, #7a7f8e)',
                  lineHeight: 1.6,
                }}>
                  {item.description}
                </p>
                {item.tags && (
                  <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                    {item.tags.map(t => (
                      <span key={t} className="badge accent">{t}</span>
                    ))}
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
