# web/docs-site

**Pitch:** static documentation site — sidebar nav, Markdown-lite content,
client-side search, dark/light theme. No external SSG framework; just
Vite + React, so you can drop it anywhere that ships static assets.

## Quick start

```bash
npm install
npm run dev        # localhost:5174
npm run build      # produces dist/
```

## Structure

| Path | What |
|------|------|
| `data/nav.json`    | Sidebar — ordered sections + pages (titles + slugs)    |
| `data/pages.json`  | Body content — `{ "<slug>": { title, body } }`          |
| `src/lib/md.tsx`   | Minimal safe Markdown renderer (headings/code/para/inline) |
| `src/lib/search.ts`| In-memory inverted-index full-text search              |
| `src/components/`  | Sidebar, DocPage, SearchBox, ThemeToggle               |

## Add a page

1. Add `{ slug, title }` to `data/nav.json` under the relevant section.
2. Add `"slug": { "title": "…", "body": "…" }` to `data/pages.json`.
3. Done — it routes via `#slug` hash.

## Swap in richer Markdown

`src/lib/md.tsx` handles headings, paragraphs, fenced code blocks, and
inline `code`. For lists, tables, links, bold/italic, install
`react-markdown` + `remark-gfm` and replace `renderMarkdown`. Keep the
output confined to React elements so the content pipeline stays
injection-safe.

## Deploy

`npm run build` → serve `dist/` from any static host
(Netlify / Vercel / GitHub Pages / S3 / Cloudflare Pages).

## Anchors

`Docusaurus`, `VitePress`, `Starlight`, `Nextra`, `mdBook`.
