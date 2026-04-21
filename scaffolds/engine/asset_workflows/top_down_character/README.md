# top_down_character

**Flag:** ANIM
**Projection:** orthographic top-down
**Coral gap:** `asset_top_down_character_001` / `asset_gamedev_top_down_character_001`
**Consumer scaffolds:** `scaffolds/gamedev/action_adventure/`, `scaffolds/gamedev/jrpg/` (see `anim_set.json` for JRPG minimal variant — this workflow is the full-ARPG set)

The canonical workflow for ARPG / top-down adventure characters. Produces per-
animation, per-direction RGBA sprite sheets from ERNIE-Image-Turbo with mode
`icon`, then slices to individual frames and stitches to per-animation master
sheets.

## Pick this over siblings when…

- You're in an overhead 2D scaffold with full 4-direction movement.
- You need a complete move-set (idle / walk / run / attack / hurt / death /
  interact), not just a 3-frame walk.
- Final per-frame size is **128×128 or 256×256** (classic ARPG / modern high-DPI).
- If your target is 48×48 RPG-Maker-style, use the `top_down_jrpg_character`
  workflow (category 5 in Shoal's plan) instead — this one over-generates
  for that scale.

## Pipeline (one call-out per anim × direction)

1. Caller fills `prompt_template.md`'s placeholders and hits ERNIE
   `/v1/images/generate` (mode=icon, steps=8, cfg=1.0, 1024×1024).
   Seed is held constant per `<character_name>` so identity stays stable
   across animations.
2. ERNIE returns a 1024×1024 RGBA sheet with the grid laid out per the
   `grid` field in `anim_set.json` for that anim (e.g. walk = 4×2 = 8 frames).
3. `postprocess.slice_grid(...)` carves it into `frame_00..frame_N-1.png` at
   the target per-frame size (128 or 256).
4. For multi-direction anims the caller repeats steps 1-3 per direction, then
   `postprocess.stitch_master(...)` stacks the per-direction sheets vertically
   into one per-animation master sheet.
5. Caller optionally `normalize_palette(...)` to quantize to a target palette
   (pico-8, gameboy, etc.) before shipping into the engine's asset pipeline.

## ERNIE call count budget

Per `anim_set.json`:

- full move-set, 4 directions: **23 calls** (~3.5 min at ~9 s/call on Turbo)
- with east→west mirror optimization: **17 calls** (~2.5 min)

West frames are produced by horizontal-flipping east frames by default; set
`directions.east_can_mirror_to_west = false` in a scaffold override if the
character has left/right-asymmetric details (single-shoulder pauldron,
holstered sidearm, etc.) that would read wrong mirrored.

## Canary corpus

Three canary renders live in this directory (see `canary_prompts.jsonl` for
the source prompts and expected-output descriptions):

- `canary_001_link_walk_south.png` — green-tunic adventurer, south walk, SNES pixel art
- `canary_002_farmer_idle_allframes.png` — Stardew-style farmer idle, pastel
- `canary_003_drifter_run_east.png` — HLD drifter, east run, neon

Each is a 256-px PNG ≤ 50 KB — embedded thumbnails only. Full-resolution
production sheets live in `workspace/asset_gen/top_down_character/` (gitignored)
and are re-generated on demand.

## Library seed

`scaffolds/engine/asset_library/top_down_character/baseline_adventurer.png` —
a canonical "green tunic adventurer" south-idle 2×2 grid that scaffolds can
either use directly or pass to `edit_image` as a style anchor for their own
character.

## Known caveats (observed in the canary corpus — read before using in anger)

### Grid-prompting does not produce true animation phases

ERNIE draws each cell of an N×M grid as a near-duplicate of the same pose,
not as successive frames of a walk / run / attack. Canary 001 and canary 003
both show 16 cells with the character in essentially one posture — clean
identity, readable silhouette, useless as an animation sheet.

**Production pattern:** do NOT prompt for `walk cycle` in one grid call. Do
one ERNIE call per frame with an explicit per-frame pose description:

- frame 0: `standing, both feet planted, weight centered`
- frame 1: `stepping, left foot lifted, knee bent to 30°`
- frame 2: `stepping, left foot forward and planted, right foot trailing`
- frame 3: `standing, both feet planted, weight on left foot`
- frame 4: `stepping, right foot lifted, knee bent to 30°`
- … and so on

The grid layout in `anim_set.json` still tells the stitcher how to combine
the per-frame outputs; it's just that generation is per-frame, not
per-sheet. The `ernie_call_count.total = 137` row in `anim_set.json` is the
honest budget — the "23 calls for a full move-set" above is the optimistic
grid path and stands only for identity/palette validation, not shippable
animation.

### Extract-bg leaves residual magenta where dark tones touch background

`/v1/workflows/icon` auto-chromakeys magenta, but character shadows and
dark cloth can overlap the magenta-adjacent region and survive the peel.
Canary 003 (HLD drifter) shows purple elliptical shadows under each cell
where the requested "soft ground shadow" hue landed too close to the
background; canary 002 (farmer) shows purple smudges at foot contacts.

**Mitigation ladder, cheapest first:**
1. `postprocess.normalize_palette(frames, max_colors=24)` — quantize to 24
   colors; fringe pink usually snaps to nearest legitimate palette entry.
2. Re-POST to `/v1/images/extract-bg` with `fringe_threshold=16` (up from
   the default 8) and `alpha_erosion_px=1` to chew back the rim.
3. If a character has a lot of dark-purple clothing that collides with the
   magenta chromakey, render against white with `mode='alpha'` (luminance
   key) instead of `mode='icon'` (magenta key) — swap at the caller.

### Top-down orthographic is not free — the prior fights you

Diffusion models trained on internet imagery default to front-facing
standing-portrait compositions. "Top-down orthographic camera directly
above" falls back to "character facing camera" roughly 30 % of the time
(canary 002 landed there; drifter canary 003 landed in pure profile
instead of true top-down). Phrases that bump the prior harder:

- `isometric projection with 30° elevation angle` — works despite asking
  for orthographic; tilts the figure credibly
- `game sprite from above, like Zelda A Link to the Past` — named
  reference games are the highest-leverage style bump
- `viewed from directly overhead, top of head visible, feet at bottom of
  frame` — spelling out the geometry beats naming the projection

If the output is stubbornly front-facing, **accept it as a reference sheet
for identity/palette and re-do pose generation per-frame with explicit
posture prompts** — don't burn seeds trying to force top-down geometry
from a decorative style phrase.

### Other small things

- ERNIE occasionally mis-grids: pose 7 lands in cell 6, pose 8 missing. If
  the slicer emits a visibly-empty final frame, regenerate with a fresh seed.
- Shadow sometimes drifts outside the cell on large-swing attacks. Shrinking
  `character_pct` to 0.22 helps but loses silhouette readability — usually
  cheaper to slice with a 2-px bleed and accept the overflow.
