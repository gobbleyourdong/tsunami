---
name: Bug Finding
applies_to: ["*"]
phase: fix
weight: strict
---

## Questions
1. Is the viewport non-blank — at least one rendered element visible above the fold?
2. Is the page free of raw stack traces, "Cannot read property" strings, "undefined is not a function" banners, or exposed "Error:" text?
3. Is every text block contained within its parent — no text overflowing containers, wrapping into sibling elements, or bleeding past edges?
4. Do all interactive controls (buttons, inputs, links) render with a visible label or icon — no empty clickable boxes?
5. Is the layout uncropped at the visible edges — no element sliced mid-word or mid-icon by the viewport boundary?
6. Are there zero broken-image placeholders visible (torn-page icon, raw alt text showing as content, missing-image X)?
7. Is z-ordering correct — no modal trapped behind content, no dropdown clipped by a sibling, no overlay swallowing the whole screen?
8. Does the primary content region fill its expected space — no ghost-white slab where a component failed to mount?
9. Are webfonts loaded — no flash-of-default-serif where the brand font should render?
10. Is styling consistent across the view — no half-styled region (e.g. raw unstyled list, light component on a dark page) indicating CSS failed to cascade?

## PASS criteria
≥ 9/10 questions answer yes unambiguously.

## FAIL criteria
Any "no" on questions 1–3 (blank viewport, runtime error surfaced to the user, or overflowing text — all ship-blockers).
