---
name: Photo Studio
applies_to: [landing, react-build, portfolio]
phase: deliver
weight: strict
---

## Questions
1. Is the hero section a SINGLE large photograph occupying 70–100% of the viewport, rather than a card grid, centered headline, or text-over-image overlay?
2. Is the headline (if visible above the fold) positioned BELOW the hero photograph, flush-left, in a serif face at 48–96px?
3. Is the top navigation tiny (12–14px) all-caps with wide letter-spacing (`tracking-[0.2em]` or similar), flushed to the right or between the wordmark and right edge?
4. Is the background either pure white (#ffffff) or near-white (#fafafa / #fcfcfa), NOT a warm cream or dark surface?
5. If an accent color is visible, is it used sparingly (< 5% of pixels) on a single hover state or hotspot, NOT as a dominant brand color?
6. Do image-frames use zero-to-minimal corner radius (0–4px), NOT large rounded cards (rounded-xl / rounded-2xl)?
7. Is metadata text (year, city, project number) rendered in tiny uppercase with tracked spacing, in a muted grey (#999 range) rather than the foreground color?
8. Is the layout free of Bento-grid asymmetries, magnetic buttons, chromatic gradients, or spring-bounce hover effects?
9. Are shadows absent or extremely subtle — no drop shadows on cards, no glow effects, just hairline borders where needed?
10. Does the page feel like a photographer's site (image-first, chrome-minimal) rather than a SaaS landing or blog?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 1, 2, 4 are load-bearing — the full-bleed image, the below-image serif headline, and the white (not cream) background are the doctrine tells.

## FAIL criteria
Any "no" on questions 1, 2, or 4. A photo_studio delivery without a full-bleed hero photograph, or with the headline ABOVE/OVERLAYING the image, or with a warm-cream background, is not photo_studio — it's another doctrine's output mislabeled.
