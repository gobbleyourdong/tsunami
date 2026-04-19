---
name: Newsroom Editorial
applies_to: [landing, react-build, blog]
phase: deliver
weight: strict
---

## Questions
1. Is the top of the page a MASTHEAD — large serif flagname centered between two hairline rules (`border-y`), with tiny uppercase metadata (Issue / Vol. / Date) above or below?
2. Is the display font a serif like Merriweather, Playfair Display, Libre Caslon, or Source Serif Pro, at 48–96px for the flagname?
3. Is there a section navigation rendered as a horizontal text list with uppercase labels and wide tracking, NOT a pill-bar or button row?
4. Is the lead article laid out as a 2-of-3 + 1-of-3 grid (lead photo + headline on the left two columns, secondary stories stacked on the right), with a vertical hairline between?
5. Is body copy rendered in a narrow column (`max-w-3xl` or `max-w-4xl`, ~65-75ch), NOT full-width or three-column wide-body?
6. Are bylines styled with italic attribution + staff-writer meta + right-aligned `tabular-nums` date — resembling a newspaper byline row?
7. Is there a visible category / breaking chip — small uppercase tracked label with a vivid-red fill (`hsl(0 100% 60%)`) or ink-on-white — NOT a pill-button or gradient badge?
8. Does any "emergency widget" signal live publication — a markets ticker, weather strip, tiny stock quote, or equivalent?
9. Is body leading `leading-snug` (≈1.375) rather than `leading-relaxed` (≈1.625)? Newspapers crowd text deliberately.
10. Does the page read as a daily paper / trade publication rather than a personal blog or magazine feature?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 1, 2, 4 are load-bearing — masthead sandwich rules, serif display, and 2/3+1/3 lead-story grid are the doctrine tells.

## FAIL criteria
Any "no" on questions 1, 2, or 7. No masthead, no serif, or no red breaking chip = drifted into magazine_editorial (quiet long-form) or shadcn_startup (utility).
