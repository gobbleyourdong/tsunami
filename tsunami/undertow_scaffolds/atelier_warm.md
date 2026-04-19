---
name: Atelier Warm
applies_to: [landing, react-build, ecommerce]
phase: deliver
weight: strict
---

## Questions
1. Is the background a WARM cream / bone / sand — `hsl(40 33% 96%)`, `hsl(30 100% 95%)`, or `hsl(35 25% 94%)` — NOT pure white (#fff) and NOT a cool grey?
2. Is foreground text a warm near-black (`hsl(30 10% 15%)`, `hsl(15 45% 20%)`) rather than pure `#000` (which reads cold against cream)?
3. Is the primary display face a gentle serif — EB Garamond, Cormorant Garamond, Libre Caslon, or Fraunces — rendered at a MODEST 40–56px (not oversized)?
4. Is italic or script used somewhere as a deliberate warmth gesture — for author names, section labels, or about-page copy?
5. Is the layout asymmetric (e.g., `grid-cols-[3fr_2fr]` or `[60%_40%]` split), NOT Swiss 50/50 or full-width stacked?
6. Are accents DESATURATED — muted terracotta `hsl(16 78% 53%)`, deep forest, oxblood, dusty plum — with saturation bounded below ~60%?
7. Is there a "colophon" signal somewhere — tiny "Est. YYYY" stamp, "Made in [City]", or handwritten-feel italic seal — NOT a generic trust badge?
8. Are shadows ABSENT (flat, borders-only) or very soft + warm-toned, NEVER heavy drop shadows or glassmorphism?
9. Is corner radius modest (0–6px) rather than large (`rounded-xl` / `rounded-2xl` / `rounded-full`)?
10. Does the page read as a handcraft / atelier / small-DTC brand rather than a SaaS dashboard, band site, or magazine?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 1, 2, 6 are load-bearing — warm-paper bg, warm-ink text, and desaturated accents define the mood.

## FAIL criteria
Any "no" on questions 1, 2, or 6. Pure white background, pure black text, or vivid saturated accents destroy the atelier voice — the delivery is in another doctrine's territory.
