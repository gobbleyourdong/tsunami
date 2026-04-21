# top_down_jrpg_character

**Flag:** ANIM (blockout shipped — animation phase future)
**Projection:** orthographic top-down, small-sprite (RPG Maker) scale
**Shoal plan category:** 5
**Consumer scaffolds:** `scaffolds/gamedev/jrpg/` (overworld party + NPC
sprites) and any scaffold targeting the retro RPG Maker aesthetic.

Fourth character workflow in the Shoal coverage set. Same character
identity (barbarian seed `20_001`) appears in all four character
workflow library slots — one character visible across four
projections + scales.

## Pick this over `top_down_character` when…

- Target output is **48×48 or 64×64** per frame (RPG Maker scale).
- Engine uses the **3-frame walk × 4 direction** convention (walk's
  middle frame = idle; no separate idle anim).
- Aesthetic is pixel-art SNES-era (Chrono Trigger / FFVI / DQ3).

If target is 128/256 px ARPG scale → use `top_down_character` (cat. 1).

## Pipeline

### Blockout (shipped here)

1. Gen at 1024×1024 with `<character_pct>` ~20% (smaller character
   than other projections — 48-px output means small source silhouette
   survives downscale).
2. Share seed across all 4 direction frames for identity preservation.
3. `postprocess.crop_to_pixel_sprite(src, out_side=48)` — alpha-bbox
   crop + pad → intermediate LANCZOS to 4× target → final NEAREST to
   48. The staged downscale is the only way to get crisp pixel-art
   output from a 1024-px source.
4. `postprocess.assemble_movement_loop_blockout(direction_to_frame,
   out_dir, cell_px=48)` — produces the 4-direction sheet using the
   shared `_common/character_blockout` helper.

### Full animation (future — `character_animation` workflow)

Expands each direction's mid-stride pose into a 3-frame walk cycle
(walk middle / left-foot-forward / walk middle / right-foot-forward).
Middle frame doubles as idle per RPG Maker convention. Total: 12
frames per character (4 dir × 3 frames).

## ERNIE call count budget

- **Blockout round (this):** 4 calls. 3-ERNIE pool wall-clock: ~18 s
  (one pipe finished the 4th fastest — the 5.7 s on pipe 8192 was the
  "wave 2" job that landed on a pipe already warmed by its first
  dispatch).
- **Full animation phase (future):** 12 calls / ~50 s single-pipe.

## Canary corpus

Three canary directions (S/E/N) + two blockout-assembly artifacts:

- `canary_001_jrpg_barbarian_S.png` — front-facing, mid-stride
- `canary_002_jrpg_barbarian_E.png` — east (right profile)
- `canary_003_jrpg_barbarian_N.png` — back-facing (walking away)
- `canary_004_blockout_4x_preview.png` — 4-direction blockout at 4×
  NEAREST magnification (for README readability)
- `canary_005_blockout_labeled.png` — labeled dev view of the blockout

## Library seeds

`scaffolds/engine/asset_library/top_down_jrpg_character/`:

- `barbarian_movement_blockout.png` (11 KB) — the 4-direction 48×48
  sheet. Actual engine-consumed artifact.
- `barbarian_movement_blockout_4x.png` (16 KB) — 4× NEAREST upscale
  for easier human inspection (not for engine consumption).
- `barbarian_movement_blockout.manifest.json` — engine cell-lookup
- `barbarian_movement_blockout.manifest.spec.json` — forward metadata
  (walk: 3 frames/direction, rotation_angles: 4)
- `barbarian_movement_blockout_preview.png` — labeled dev view

## Cross-projection identity

**Same barbarian identity across all four character workflow library
slots:**

- `iso_character/barbarian_movement_blockout.png` — 8 dirs × 2:1 dimetric
- `top_down_character/barbarian_movement_blockout.png` — 4 dirs × 256px
- `side_scroller_character/barbarian_movement_blockout.png` — 1 dir × 256px
- **`top_down_jrpg_character/barbarian_movement_blockout.png`** — 4 dirs × 48px

One character, four projections. Scaffolds pick the projection that
matches their engine without re-establishing the character. Future
`character_animation` workflow reads the matching `.manifest.spec.json`
from any of the four slots and interpolates uniformly.

## Findings from this round

### Staged downscale (LANCZOS → NEAREST) produces clean pixel-art

Direct NEAREST from 1024 → 48 loses too much character detail. Pure
LANCZOS smears pixel edges into mush. Staged (1024 → 192 LANCZOS → 48
NEAREST) preserves structural feature outlines while snapping to the
pixel grid at the final step. Documented in `postprocess.crop_to_pixel_sprite`.

### SNES-era prompting lands beautifully

"SNES-era 16-bit pixel-art style with limited 32-color palette" + "hard
1-pixel edges" + "no antialiasing bleed" gave clean canary outputs
that compress to 8-10 KB each. Pixel-art style variant is more
reliably applied than other style_variants (consistent finding from
`vfx_library` canary 002 pixel fire).

### 20% subject pct matters at this scale

The prompt spells out "character occupies ~20% of the canvas" — smaller
than other workflows' 25-30%. At 1024-px gen, that's a ~200-px character
with detail budget enough to survive 48-px downscale. Bigger subjects
in the canvas would have intricate detail that smears in the final
NEAREST step.
