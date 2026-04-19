---
name: Brutalist Web
applies_to: [landing, react-build]
mood: raw, anti-polish, Are.na / Yale School of Art / Balenciaga / Cash App old
default_mode: light
anchors: (none in scraped corpus — aspirational/escape-hatch doctrine)
---

## Evidence note

**0/155 matches in the scraped scraped corpus.** The drone's user base does
not ship brutalist. This doctrine is kept for the case where a user explicitly
asks for it (keyword "brutalist" / "anti-design" / "raw html") — it's an
escape-hatch, not a default. If you landed here via random selection, you are
almost certainly in the wrong doctrine; prefer `shadcn_startup` or
`photo_studio` unless the user brief demands rawness.

## Palette
- Hard white `#ffffff` background
- Pure black `#000000` text
- ONE clashing hot: `#ff0000`, `#00ff00`, `#ffff00`, or `#ff00ff`
- No greys. No gradients. No shadows. No rounded corners.

## Typography
- System default stacks exposed: `Times New Roman, serif` or `Courier New, monospace`
- Bold for weight, not weight-700 fonts. Use `<b>` or `font-bold`.
- ALL CAPS for headings. Wide tracking (`tracking-wider`).
- No custom webfont. Accept browser defaults.

## Layout bias
- Raw HTML defaults: `<h1>`, `<ul>`, `<table>` styled minimally
- Ragged right, no justification, no hyphenation
- 1px hard borders between EVERY element. Solid, black, no softening.
- Content edge-to-edge. No max-width container. No padding on body.

## Motion
- None. Instant. Clicks produce instant page changes.
- The only permitted "motion": 1px translate on hover to show clickability.
- No transitions, no animations, no framer-motion `motion.*` wrappers.

## Structural moves
- Navigation as an unstyled `<ul>` at the top, horizontal via `display: flex`
- Inline data tables for specs — `<table>` with visible borders
- Links are underlined blue `#0000ee`, visited are purple `#551a8b`. Yes, 1995.
- Images with no treatment — no rounded corners, no shadow, no border radius
- Timestamp / byline in the top-right like a news article

## Structural DO-NOTs
- No cards. No shadows. No rounded anything. No smooth gradients. No blur effects.
- No "hero section" with image + overlay. Just a headline and a paragraph.
- No centered layouts. Left-align everything.
- No hover scales, no parallax, no scroll-linked effects.

## Reference sites to emulate
- are.na, yale.edu/art, craigslist.org, berghain.berlin, balenciaga.com
- Early Bloomberg Businessweek, Apartmento classifieds, Eye Magazine archives
