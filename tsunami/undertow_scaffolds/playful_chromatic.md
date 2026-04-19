---
name: Playful Chromatic
applies_to: [landing, react-build, form-app]
phase: deliver
weight: strict
---

## Questions
1. Is the background a WARM off-white (`#fdfcf8`, `#fcf8f3`) — never pure white and never dark?
2. Is the primary display face an expressive modern sans — Syne, Bricolage Grotesque, Onest, or Miranda Sans — at a bold weight (600+)?
3. Is there a visible mesh gradient blob / radial-gradient accent somewhere behind the hero, using two of three warm chromatic hues (coral `#ff6b6b`, mint `#4ecdc4`, butter `#ffe66d`)?
4. Are multiple accent colors used TOGETHER (2-3 chromatic accents visible on the same viewport), NOT reserved for a single CTA?
5. Is the top navigation a sticky pill-shaped bar (`rounded-full`) that contrasts against the background with soft blur?
6. Do decorative elements include slight rotation — `rotate-[-1deg]` or `rotate-[1deg]` on cards/blocks — suggesting hand-placement rather than rigid grid?
7. Is the layout a BENTO grid (mixed tile sizes — 2×2, 1×2, 1×1 in the same row), NOT a uniform 3-up equal grid?
8. Are corner radii consistently large (16–32px) across cards, buttons, and input fields?
9. Is motion SPRING-based — `transition: { type: "spring", bounce: 0.3 }` or equivalent — with `hover:-translate-y-1` lift on interactive elements?
10. Does the page read as a playful lab / creative studio / Framer-style expressive marketing site, NOT utility SaaS or editorial?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 2, 3, 7 are load-bearing — expressive display sans, chromatic gradient accent, bento mixed-size grid.

## FAIL criteria
Any "no" on questions 1, 2, or 7. Pure white bg, neutral sans, or rigid 3-up grid = playful_chromatic lost its flavor and became shadcn_startup.
