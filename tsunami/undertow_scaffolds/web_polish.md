---
name: Web Polish
applies_to: ["*"]
phase: polish
weight: advisory
---

## Questions
1. Is primary navigation (top bar, sidebar, or equivalent) identifiable within two seconds of looking at the screenshot?
2. Is there a clear primary call-to-action on screen — one button or link that reads as "the thing to do next"?
3. Is content density appropriate for the brand posture — luxury / editorial heroes legitimately run headline-only in deep negative space; dashboard / utility surfaces need more information per screen. Flag only when density contradicts the apparent intent (three words on an admin panel; wall-of-text on a hero).
4. Is there breathing room between major sections — detectable gutters, nothing touching viewport edges?
5. Is body-text contrast sufficient — copy readable against its background at a glance?
6. Are interactive elements sized for comfortable clicking — not tiny, not absurdly oversized?
7. Is alignment consistent — column edges line up, headings share a left margin, no stray centred element inside a left-aligned block?
8. Does the screen have a recognisable information hierarchy — heading > subheading > body > supporting?
9. Are visual states clear where present — hover, active, disabled distinguishable from default?
10. Is the surface free of obvious placeholder content ("Lorem ipsum", "TODO", "Label goes here", "Your content here")?

## PASS criteria
≥ 7/10 questions answer yes unambiguously.

## FAIL criteria
Any "no" on questions 1, 2, or 10 (nav identifiability, primary CTA, or placeholder text leaking into delivery).
