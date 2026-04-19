---
name: Vision Analysis
applies_to: ["*"]
phase: audit
weight: strict
---

## Questions
1. Does the screenshot's primary subject match the noun phrase in the user's request (request says "dashboard" → a dashboard is visible)?
2. Is the dominant content region where a reader's eye lands first the subject the user asked for — not a stray banner, placeholder, or error modal?
3. Does the screenshot contain the key feature words from the request (request says "pricing table" → a pricing table is visible)?
4. Is the composition deliberate — clear foreground, readable hierarchy, no single centred element floating in empty whitespace?
5. Is lighting / contrast sufficient — body text readable against its background without squinting?
6. Is the subject rendered at a sensible scale — not thumbnail-sized in empty space, not cropped so tightly that context is lost?
7. Are there zero obvious contradictions between the request and the image (request says "dark mode" → the screenshot is clearly dark)?
8. Does the viewport framing show the deliverable itself rather than browser chrome, scrollbars, or devtools?
9. Is the image a single coherent artifact — not two half-rendered states stacked, not a torn loading frame?
10. Would a reader shown only this screenshot correctly guess what the user asked for?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Question 10 must be yes.

## FAIL criteria
Any "no" on questions 1, 2, or 10 (subject mismatch — the artifact does not depict what was requested).
