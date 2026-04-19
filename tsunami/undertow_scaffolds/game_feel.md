---
name: Game Feel
applies_to: [gamedev]
phase: deliver
weight: advisory
---

## Questions
1. Is the player character or player cursor immediately identifiable as the focal element on screen?
2. Is current game state readable at a glance — score, health, resources, or objective visible without hunting?
3. Does the HUD occupy screen edges or corners rather than obstructing the play field?
4. Is there visible feedback for the last action in the frame — hit spark, damage number, particle, squash-stretch, or motion trail?
5. Are enemies and interactive objects visually distinct from background decoration?
6. Is the palette directing attention — important objects saturated, background desaturated or lower contrast?
7. Is camera framing sensible — player not jammed into a corner, dead zone reasonable, no excessive empty screen?
8. Is movement state legible — you can tell the character is running, jumping, attacking, or idle from one frame?
9. Are UI prompts and pickups scaled relative to the player so hit-confidence is obvious?
10. Does the scene read as "playable" rather than as a static mockup — motion lines, trails, or mid-action poses visible?

## PASS criteria
≥ 7/10 questions answer yes unambiguously.

## FAIL criteria
Any "no" on questions 1, 2, or 5 (player identifiable, state readable, enemies distinct from background — all play-breaking).
