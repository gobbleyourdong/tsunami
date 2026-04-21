import { getPage } from "../data/docs"
import { renderMarkdown } from "../lib/md"

export default function DocPage({ slug }: { slug: string }) {
  const page = getPage(slug)
  if (!page) return <article className="content"><h1>Not found</h1></article>
  return <article className="content">{renderMarkdown(page.body)}</article>
}
