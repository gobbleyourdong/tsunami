# web/blog

**Pitch:** post list + detail + tag filter. React + Vite + TS. Content
lives in `data/posts.json` so your writing-to-deploy flow is:
edit the JSON, `npm run build`, push. Works well with a static host.

## Quick start

```bash
npm install
npm run dev        # localhost:5176
```

## Structure

| Path | What |
|------|------|
| `data/posts.json`      | Seed posts — slug/title/date/tags/author/excerpt/body |
| `src/data/posts.ts`    | Typed access + tag/sort helpers                         |
| `src/lib/md.tsx`       | Minimal safe Markdown renderer (same as docs-site)      |
| `src/components/`      | PostList, PostDetail, TagBar                            |

## Add a post

Append to `data/posts.json`:

```json
{
  "slug": "my-new-post",
  "title": "My New Post",
  "date": "2026-04-20",
  "tags": ["tag1", "tag2"],
  "author": "you",
  "excerpt": "One-line hook.",
  "body": "# My New Post\n\nBody in Markdown."
}
```

Slugs must be unique and URL-safe. Routing uses hash (`#slug`).

## Swap Markdown renderer

`src/lib/md.tsx` handles the basics. For lists, tables, links,
install `react-markdown` + `remark-gfm` and replace `renderMarkdown`.
See the docs-site scaffold's README for the same note — these two
share the minimal renderer.

## Deploy

`npm run build` → ship `dist/` to any static host.

## Anchors

`Jekyll`, `Hugo`, `Eleventy`, `Astro`, `Ghost`, `hashnode`.
