import { byTag, type Post } from "../data/posts"

type Props = { tag: string; onSelect: (slug: string) => void }

export default function PostList({ tag, onSelect }: Props) {
  const list = byTag(tag)
  if (list.length === 0) {
    return <div style={{ padding: "2rem 0", color: "#888" }}>No posts yet.</div>
  }
  return (
    <div>
      {list.map((p: Post) => (
        <article
          key={p.slug}
          className="post-card"
          onClick={() => onSelect(p.slug)}
        >
          <h2>{p.title}</h2>
          <div className="post-meta">
            {formatDate(p.date)} · {p.tags.join(" · ")}
          </div>
          <div className="post-excerpt">{p.excerpt}</div>
        </article>
      ))}
    </div>
  )
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric", month: "long", day: "numeric",
  }).format(d)
}
