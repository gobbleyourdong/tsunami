import navData from "../../data/nav.json"
import pagesData from "../../data/pages.json"

export type Page = { title: string; body: string }
export type NavSection = { title: string; pages: { slug: string; title: string }[] }

export const nav: { sections: NavSection[] } = navData as never
export const pages: Record<string, Page> = pagesData as never

export function listSlugs(): string[] {
  return Object.keys(pages)
}

export function getPage(slug: string): Page | undefined {
  return pages[slug]
}
