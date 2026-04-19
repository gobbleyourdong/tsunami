---
name: Editorial Dark
applies_to: [landing, react-build, dashboard]
phase: deliver
weight: strict
---

## Questions
1. Is the background near-black — `#0a0a0a` or `#111` — with at most 1-2 elevation tints (`#1a1a1a`, `#282828`), NOT pure black (#000) and NOT a tinted-dark?
2. Is the primary display face a LUXURY SERIF — Playfair Display, Cormorant Garamond, GT Sectra, or Instrument Serif — NOT a condensed display sans (that's cinematic_display)?
3. Is the layout an ASYMMETRIC 7fr / 5fr split (`grid-cols-[7fr_5fr]`), NOT a 50/50 balanced grid or a full-bleed centered composition?
4. Is one column a STICKY image region (`sticky top-[10vh]`) while the other scrolls — creating the "text scrolls past image" effect typical of Apple product pages?
5. Are grey text tones created with OPACITY tiers (`text-[#f5f5f5]/60`, `/20`), NOT with mid-grey hex values?
6. Is there ONE accent gesture (gold, copper, forest, oxblood, arctic blue) used at < 5% of pixels — on a single hover state or hotspot?
7. Is the section-break pattern a horizontal pull-quote breaker — serif italic text at 32–40px, centered with generous padding — or an uneven section-height rhythm (70vh / 45vh / 110vh)?
8. Do number-led stat rows appear ("01 — 1,700 km" or similar), with display-weight numerals in the serif face?
9. Is motion SPRING-easing with subtle scale hovers (1.01-1.02, 600-800ms), NEVER bouncy or rapid?
10. Does the page read as Apple / Tesla / The Row / Kettle luxury brand rather than a band site (cinematic) or utility (shadcn)?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 1, 2, 3 are load-bearing — near-black (not pure-black), luxury serif (not display sans), and 7/5 asymmetric split define the doctrine.

## FAIL criteria
Any "no" on questions 2 or 3. An editorial_dark delivery using a condensed display sans (Bebas/Anton) is cinematic_display; a balanced 50/50 grid is generic dark utility. Both are drift.
