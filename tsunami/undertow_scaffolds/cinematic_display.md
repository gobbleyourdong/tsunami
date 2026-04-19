---
name: Cinematic Display
applies_to: [landing, react-build]
phase: deliver
weight: strict
---

## Questions
1. Is the background pure black (#000) or near-black (#0a0a0a / `hsl(0 0% 4%)`), NOT a dark-blue or dark-grey surface?
2. Is the primary display type a condensed bold sans — Bebas Neue, Anton, Archivo Black, or Oswald — rendered in UPPERCASE with wide tracking (`tracking-widest`)?
3. Is the hero headline genuinely oversized — 120px+ on desktop, filling a large portion of viewport width?
4. Is the hero a 100vh full-bleed composition (video loop OR single photograph) with a dark scrim gradient lifting the type off the image?
5. Is the navigation a translucent `bg-background/30` or `bg-background/80` strip with `backdrop-blur-md`, containing tiny 12-14px uppercase links?
6. Is body text pure white `#ffffff` (or high-opacity white like `text-white/80`), NOT a mid-grey "muted" color?
7. If a ticking marquee of dates / titles / venues is present at bottom, does it read as a single horizontal strip with uppercase tracked text?
8. Are shadows and rounded corners absent? Edges should be hard — 1px white rules between sections, no `rounded-xl` cards.
9. Is the one permitted accent color (if visible) a high-chroma choice — electric yellow, hot red, or retained neutral grey — used sparingly?
10. Does the page read as a band/film/nightclub site (mood: loud, oversized, full-bleed) rather than a content-dense utility page?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 1, 2, 3 are load-bearing — near-black bg, condensed display caps, and oversized type are the doctrine's defining triad.

## FAIL criteria
Any "no" on questions 1, 2, or 3. A cinematic_display delivery on a light background, with a thin-weight serif, or with headlines under 80px is not cinematic_display — it drifted into another doctrine.
