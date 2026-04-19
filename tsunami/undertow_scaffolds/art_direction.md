---
name: Art Direction
applies_to: [landing, dashboard, react-build, form-app]
phase: deliver
weight: strict
---

## Questions
1. Is there a single dominant colour occupying > 40% of pixels, with at most two accent colours beyond neutrals?
2. Do text elements use at most two typefaces across the entire screenshot?
3. Is the type scale restrained — at most four distinct text sizes visible in one viewport?
4. Is there a consistent corner-radius idiom — cards, buttons, inputs all either sharp or all rounded to a similar radius?
5. Are spacing gaps multiples of a single base unit (4 px or 8 px) — no arbitrary 13 px or 27 px gutters?
6. Is the palette internally consistent — near-black (#0a-#12 range) or near-white (#f5-#fc range) backgrounds are fine when used deliberately; flag only when a page mixes very-dark sections with very-light sections that weren't a chosen contrast move?
7. Are interactive elements visually distinct from static text — buttons read as pressable, links read as clickable?
8. Is visual weight balanced across the composition — no quadrant that's dense while the others are empty?
9. Do shadows, borders, and gradients follow one discipline — all flat, or all soft-shadow, or all glassmorphic — not a mix?
10. Is imagery (icons, illustrations, photos) stylistically coherent — no flat icons next to glossy 3D renders next to stock photos?

## PASS criteria
≥ 8/10 questions answer yes unambiguously.

## FAIL criteria
Any "no" on questions 1–3 (colour discipline and typography discipline — a mixed palette or four typefaces reads as amateur regardless of other polish).
