---
name: Brutalist Web
applies_to: [landing, react-build]
phase: deliver
weight: strict
---

## Questions
1. Is the background HARD WHITE (#ffffff) with NO off-white / cream / grey tint at all?
2. Is typography rendered in the system default stacks — `Times New Roman, serif` OR `Courier New, monospace` — with NO custom web font loaded from Google Fonts or elsewhere?
3. Are headings ALL-CAPS with wide tracking, rendered in the same default serif/mono — NOT in a display sans?
4. Is there ZERO corner radius anywhere? All cards, buttons, inputs, images must be sharp rectangles.
5. Is there ZERO drop shadow or blur effect anywhere on the page?
6. Are element boundaries rendered as SOLID 1px black borders (`border: 1px solid #000`) — NOT semi-transparent, NOT rounded, NOT colored?
7. Are links rendered in underlined 1995-blue (`#0000ee`) with purple visited state (`#551a8b`) — yes, literally — NOT the scaffold's accent color?
8. Is ONE clashing hot color visible — pure `#ff0000`, `#00ff00`, `#ffff00`, or `#ff00ff` — used as a brand statement, NOT as a subtle accent?
9. Is the layout edge-to-edge with NO max-width container and NO centered hero? Left-aligned raw, NOT padded-center?
10. Is motion entirely ABSENT — no transitions, no hover scales, no fades — other than a 1px translate on hover to signal clickability?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 1, 2, 4 are load-bearing — hard white bg, default-stack type (NOT Google Fonts), and zero rounded corners define brutalist.

## FAIL criteria
Any "no" on questions 1, 2, 4, or 5. A brutalist delivery with rounded corners, drop shadows, a custom web font, or an off-white bg is NOT brutalist — it's a polished aesthetic with anti-design cosplay and should be reclassified.

## Note
This doctrine is KEYWORD-ONLY — it has 0 weight in corpus-weighted random selection. If it appears as `style_name`, the user asked for it explicitly. The rubric can be strict without worrying about false failures on random-selected deliveries.
