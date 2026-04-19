---
name: Sprite Quality
applies_to: [gamedev]
phase: deliver
weight: strict
---

## Questions
1. Are sprite edges pixel-clean — no halo of semi-transparent anti-aliased fringe around the silhouette on a contrasting background?
2. Is the sprite silhouette readable — you can identify the character from outline alone, not an ambiguous blob?
3. Is the pixel grid consistent — all sprites rendered at the same base resolution, no mixing of 16 px and 32 px assets at the same zoom?
4. Is scaling clean — integer-multiple upscales (2×, 3×, 4×) rather than fractional blurry upscales?
5. Are jaggies deliberate where curves should read as curves — circles look circular via considered stair-stepping, not random aliasing?
6. Is the colour count disciplined — a limited palette (≤ 32 colours per sprite) rather than a gradient soup?
7. Do sprites align on the sprite-sheet grid — no half-pixel offset causing shimmer between frames?
8. Is lighting direction consistent across sprites — all lit from the same angle (typically top-left)?
9. Are outlines (if used) uniform thickness — no 2-px edge on one side and 1-px on the other?
10. Do animation frames hold pose clarity individually — each frame readable on its own, not a mid-tween mush?

## PASS criteria
≥ 8/10 questions answer yes unambiguously.

## FAIL criteria
Any "no" on questions 1, 2, or 3 (dirty edges, unreadable silhouette, or mixed pixel resolutions — foundational pixel-art failures).
