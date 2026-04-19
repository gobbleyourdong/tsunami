---
name: Editorial Dark
applies_to: [landing, react-build, dashboard]
mood: luxury, cinematic, Apple / Tesla / Kettle / The Row
---

## Palette
- Base: near-black `#0a0a0a` with 1-2 elevation tints `#111`, `#1a1a1a`
- Text: `#f5f5f5` primary, `#f5f5f5/60` secondary, `#f5f5f5/30` tertiary
- One brand accent, used with restraint (< 5% of pixels) — gold, copper, forest, oxblood, arctic blue
- No gradients except controlled 2-stop fades on imagery (hero overlay, image bottom vignette)

## Typography
- Display: large serif — `Playfair Display`, `Cormorant Garamond`, `GT Sectra`, or `Editorial New`. Weight 400-500. Tight tracking.
- Body: neutral sans — `Inter`, `Söhne`, `Neue Haas Grotesk`. Weight 400. Comfortable 1.6 line-height.
- Scale: 72px+ display, 40px H1, 24px H2, 16px body, 13px caption, 11px micro. Skip 2 steps between each.
- Numerals: tabular for specs (`font-variant-numeric: tabular-nums`).

## Layout bias
- Asymmetric: 7fr / 5fr splits, not 6/6. Negative space dominates.
- Heroes are NOT centered — text left-aligned at bottom-left or bottom-right, large photo fills rest.
- Sections are uneven heights — 70vh, 45vh, 110vh — never uniform.
- Gutters: 8px base unit, sections spaced 120-160px apart vertically.

## Motion
- Spring easing, not linear. `transition: { type: "spring", stiffness: 80, damping: 20 }`.
- Scroll-linked: image parallax at 0.4x, text at 1.0x. Use framer-motion `useScroll` + `useTransform`.
- Hover: subtle scale 1.01-1.02 + brightness 1.05, 600-800ms. Never bouncy.
- Page transitions: crossfade with 400ms delay on incoming content. No slide.

## Structural moves that read current
- Sticky image column, scrolling text column (position: sticky; top: 10vh)
- Horizontal section break: large quote, mid-weight serif, italics, max-w-3xl, centered
- Drop cap on long-form (first letter 5x size, float left, serif)
- Number-led stat rows: "01 — 1,700 km" not "1700 / km" — number gets the weight
- Bento for collections: 2x1 hero tile + three 1x1 tiles, not uniform grid

## Reference sites to emulate
- apple.com/iphone, tesla.com/model-s, thepeaq.co, kettle.co
- Editorial magazines: nytimes.com/interactive features, wallpaper.com, kinfolk.com
