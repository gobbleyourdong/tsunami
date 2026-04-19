---
name: Playful Chromatic
applies_to: [landing, react-build, form-app]
mood: warm, expressive, Stripe / Linear / Vercel / Framer early
---

## Palette
- Warm off-white `#fdfcf8` or `#fcf8f3` (never pure white)
- Soft ink text `#1f1b18` (never pure black)
- Three accents used together, NOT reserved: coral `#ff6b6b`, mint `#4ecdc4`, butter `#ffe66d`
- Gradients ARE permitted — 2-stop soft mesh backgrounds on hero / card accents

## Typography
- Display: friendly geometric sans — `Clash Display`, `Gambarino`, `Satoshi`, `PP Editorial New`
- Body: same family lighter weight, or complementary like `General Sans`, `Söhne`
- Ligatures enabled (`font-feature-settings: "liga", "dlig"`)
- Variable axis play: let headings have `font-variation-settings: "wght" 550, "wdth" 115` for character

## Layout bias
- Tile-based bento grids with varied sizes — some tiles 2x2, some 1x2, some 1x1
- Organic asymmetry — slight rotations on cards (`rotate: -1deg`), staggered alignment
- Rounded radii 16-24px on everything, consistently
- Layered elements — a tag badge overlapping the corner of a card, a logo breaking out of its container

## Motion
- Spring-physics everything. `transition: { type: "spring", bounce: 0.35 }`.
- Hover lifts: `translateY(-4px)` + soft shadow intensify
- Cursor-reactive: magnetic buttons that nudge toward the cursor
- Sequential reveal on scroll: children stagger in 80ms apart
- Loading state: skeleton shimmer with the accent gradient

## Structural moves
- Sticky pill-shaped navigation that shrinks on scroll
- Hover-reveal color swatches: grey state → color-wash on mouseover
- Interactive metrics: hover a number and it animates to a new value (alternate stat)
- Playful empty states: illustration + witty copy, not just "No results"
- Custom cursor: a dot that scales to 40px over interactive elements

## Reference sites to emulate
- stripe.com, linear.app, vercel.com, framer.com, raycast.com
- Personal sites: brittanychiang.com, rauno.me, jhey.dev
