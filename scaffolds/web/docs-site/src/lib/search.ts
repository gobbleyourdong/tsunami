import { pages, type Page } from "../data/docs"

export type SearchHit = { slug: string; title: string; snippet: string }

/**
 * Tiny inverted-index search. Builds once per session on module load;
 * queries are O(query tokens × matching slugs). Good enough to tens of
 * thousands of words; swap for MiniSearch / lunr if you need BM25
 * scoring, stop-word handling, or stemming.
 */
const index = buildIndex()

function tokenize(s: string): string[] {
  return s.toLowerCase().match(/[a-z0-9]+/g) ?? []
}

function buildIndex(): Map<string, Set<string>> {
  const out = new Map<string, Set<string>>()
  for (const [slug, page] of Object.entries(pages)) {
    const toks = new Set([...tokenize(page.title), ...tokenize(page.body)])
    for (const t of toks) {
      let set = out.get(t)
      if (!set) { set = new Set(); out.set(t, set) }
      set.add(slug)
    }
  }
  return out
}

export function search(query: string, limit = 10): SearchHit[] {
  const toks = tokenize(query)
  if (toks.length === 0) return []

  const score = new Map<string, number>()
  for (const t of toks) {
    const hits = index.get(t)
    if (!hits) continue
    for (const slug of hits) score.set(slug, (score.get(slug) ?? 0) + 1)
  }

  const ranked = [...score.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)

  return ranked.map(([slug]) => {
    const page = pages[slug] as Page
    const body = page.body
    const first = toks.find(t => body.toLowerCase().includes(t)) ?? ""
    const pos = first ? body.toLowerCase().indexOf(first) : 0
    const snippet = body.slice(Math.max(0, pos - 30), pos + 60).replace(/\n/g, " ")
    return { slug, title: page.title, snippet }
  })
}
