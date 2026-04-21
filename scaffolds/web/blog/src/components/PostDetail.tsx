import { findPost } from "../data/posts"
import { renderMarkdown } from "../lib/md"

type Props = { slug: string; onBack: () => void }

export default function PostDetail({ slug, onBack }: Props) {
  const post = findPost(slug)
  if (!post) {
    return (
      <article className="post-detail">
        <button className="back" onClick={onBack}>← Back</button>
        <h1>Not found</h1>
      </article>
    )
  }
  return (
    <article className="post-detail">
      <button className="back" onClick={onBack}>← Back</button>
      <h1>{post.title}</h1>
      <div className="post-meta">
        {new Intl.DateTimeFormat("en-US", {
          year: "numeric", month: "long", day: "numeric",
        }).format(new Date(post.date))} · {post.author} · {post.tags.join(" · ")}
      </div>
      {renderMarkdown(post.body)}
    </article>
  )
}
