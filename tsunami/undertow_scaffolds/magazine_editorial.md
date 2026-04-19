---
name: Magazine Editorial
applies_to: [landing, react-build]
phase: deliver
weight: strict
---

## Questions
1. Is the background cream or newsprint — `#f6f1e8`, `#ede8dc`, `hsl(40 33% 96%)`, or similar warm neutral — NOT pure white and NOT dark?
2. Is there a two-family typographic system visible — a serif display (Playfair Display / DM Serif Display / GT Sectra) + a neutral sans or body serif?
3. Does an opening long-form paragraph use a DROP CAP — first letter floating left, 5+ lines tall, in the display serif?
4. Is long-form body copy rendered in a MULTI-COLUMN layout (`[column-count:2]` or `columns-2`) at desktop width, mimicking print?
5. Are pull quotes styled as serif italic at 32–40px, breaking the column grid, right-aligned or centered, with hairline rules above AND below?
6. Is there a visible "section opener" somewhere — a large numbered section marker (`01` / `02` in huge serif) with a title and lots of white space?
7. Is there a byline / issue / date metadata row — italic attribution + uppercase tracked caption text — styled like a magazine feature opener?
8. Are images below-body (not in-flow hero) captioned with small italic text and a thin rule above, resembling print fig captions?
9. Is accent color muted — terracotta `#c76b4a`, forest `#2d4a3e`, navy `#1a2b4a`, oxblood — rather than vivid chromatic?
10. Does the page read as a long-form Kinfolk / NYT-feature magazine, not a newsroom (urgent) or atelier (small-brand)?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 2, 3, 4 are load-bearing — two-family serif system, drop cap, and multi-column body are the doctrine's print-inspired tells.

## FAIL criteria
Any "no" on questions 2, 3, or 4. A magazine_editorial delivery without a serif display, drop cap, or multi-column body has lost the print-magazine character — it's running as a generic blog.
