---
name: Swiss Modern
applies_to: [dashboard, data-viz, landing, react-build]
phase: deliver
weight: strict
---

## Questions
1. Is the layout on a STRICT 12-column grid (`grid-cols-12 gap-4`) with visible column discipline — nav items, hero sections, and footers all land on shared column boundaries?
2. Is the background off-white (`#fafaf7` / `#f0eee8`) or near-white with slight warmth, NOT pure white and NOT dark?
3. Is the typography ONE family at three weights max (Inter / Neue Haas Grotesk / Archivo / Host Grotesk), with NO italics, NO serifs, NO display faces?
4. Is there ONE single saturated accent color — Helvetica-red `#e30613`, cobalt `#0047ab`, or chrome-yellow `#ffcc00` — used ONLY for the single primary CTA, NOT scattered across multiple elements?
5. Do section boundaries use single-pixel hairline rules (`border-t border-[#111]`), NOT padding-only gaps or heavy drop shadows?
6. Are numbered section markers (01 / 02 / 03) visible in a narrow left-column gutter, or in the top corner of sections?
7. Are label-value data pairs aligned in rigid columns (`[120px_1fr]` grid or colon-aligned), NOT flowing freely?
8. Is there a "section count" footer somewhere — "03 / 08" or similar `tabular-nums` marker tracking progress through the document?
9. Are animation and motion MINIMAL — 200ms opacity fade at most, NO spring physics, NO hover scale, NO parallax?
10. Does the page read as a rigorous Müller-Brockmann / Base Design studio site rather than a utility SaaS, magazine, or portfolio?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 1, 3, 4 are load-bearing — strict 12-col grid, single sans family, ONE saturated accent are the Swiss Modern triad.

## FAIL criteria
Any "no" on questions 1, 3, or 4. A swiss_modern delivery without a 12-col grid, or with multiple font families, or with multiple scattered accent colors, is not Swiss Modern — it's drifted into shadcn_startup or playful territory.
