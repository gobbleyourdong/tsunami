import raw from "../../data/posts.json"

export type Post = {
  slug: string
  title: string
  date: string
  tags: string[]
  author: string
  excerpt: string
  body: string
}

export const posts: Post[] = (raw as { posts: Post[] }).posts

export function findPost(slug: string): Post | undefined {
  return posts.find(p => p.slug === slug)
}

export function allTags(): string[] {
  const set = new Set<string>()
  for (const p of posts) for (const t of p.tags) set.add(t)
  return Array.from(set).sort()
}

export function byTag(tag: string): Post[] {
  if (!tag) return sortedByDate(posts)
  return sortedByDate(posts.filter(p => p.tags.includes(tag)))
}

export function sortedByDate(list: Post[]): Post[] {
  return [...list].sort((a, b) => b.date.localeCompare(a.date))
}
