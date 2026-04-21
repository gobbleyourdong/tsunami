# iso_character

**Flag:** ANIM (blockout shipped — animation phase future)
**Projection:** isometric 2:1 dimetric (26.57° elevation)
**Shoal plan category:** 2
**Consumer scaffolds:** any isometric scaffold (future `scaffolds/gamedev/iso/`,
ARPG in iso projection, strategy games)

First Shoal workflow built on the **blockout-first discipline**: ships
one canonical mid-stride pose per direction (8 directions), shared seed
for identity preservation, and hooks into future animation + rotation
workflows.

## Pick this over siblings when…

- The scaffold is isometric / 2:1 dimetric (Diablo / Fallout Tactics /
  Hades / Landstalker).
- You need 8-direction characters (or fewer — 4-direction works too;
  just pick a subset from `ISO_DIRECTIONS_8`).
- You want a **movement-loop blockout** as the first deliverable —
  prove silhouette, identity, combat timing, and collision bounds
  before spending full-animation budget.

## Pipeline

### Phase 1: blockout (shipped here)

1. Fill `prompt_template.md` with one constant `<character_name>` and
   `<movement_pose_description>`.
2. For each direction in `ISO_DIRECTIONS_8` (`N/NE/E/SE/S/SW/W/NW`):
   - vary only `<direction_description>`
   - pin the **same seed** across all 8 calls — identity lever
   - hit ERNIE `/v1/workflows/icon`
3. `postprocess.crop_frame(src, out_dir, out_side=256)` on each frame.
4. `postprocess.assemble_movement_loop_blockout(direction_to_frame,
   out_dir, character_id)` → writes:
   - `{id}_movement_blockout.png` — 4×2 sprite sheet
   - `{id}_movement_blockout.manifest.json` — cell coords + direction
     labels (engine source of truth)
   - `{id}_movement_blockout.manifest.spec.json` — forward-looking
     metadata (`anim_frame_targets`, `rotation_angles`) for the
     downstream animation + rotation workflows
   - `{id}_movement_blockout_preview.png` — labeled dev view

### Phase 2: full animation (future — `character_animation` workflow)

Reads `blockout.spec.json::anim_frame_targets` = {idle: 4, walk: 8, run: 8,
attack: 6, hurt: 3, death: 6, cast: 5} and runs `edit_image` on each
blockout direction's baseline pose to interpolate outward into N frames
per anim per direction. Total target: **320 frames** per character
(8 dir × 40 per-direction frames across 7 anims).

### Phase 3: rotation up-res (future — `character_rotation` workflow)

Reads `blockout.spec.json::rotation_angles` (default 8; can be raised to
16/32/64) and interpolates between the 8 cardinal/ordinal directions
to produce sub-angle rotated frames for fake-3D iso effects.

## ERNIE call count budget

- **Blockout round (this workflow):** 8 calls (one per direction).
  Wall-clock: ~45 s single-pipe, ~24 s with 3-ERNIE pool (limited by
  GPU compute at 1024 px — ~1.4× speedup).
- **Animation phase (future):** 320 calls per character.
- **Rotation up-res (future, 16-angle):** +128 calls per character.

## Canary corpus

Three direction-specific canaries + two blockout-assembly canaries:

- `canary_001_iso_barbarian_S.png` — south-facing (front) barbarian
- `canary_002_iso_barbarian_E.png` — east-facing (right profile)
- `canary_003_iso_barbarian_NE.png` — north-east-facing (3/4 back-right)
- `canary_004_movement_blockout_sheet.png` — 4×2 sprite sheet of all
  8 directions (what the engine consumes)
- `canary_005_movement_blockout_preview.png` — labeled dev view

All rendered via the 3-ERNIE pool — 3 original directions in 14 s,
remaining 5 directions in 24 s.

## Library seeds

`scaffolds/engine/asset_library/iso_character/`:
- **Barbarian** (hero character — seed `20_001`):
  - `barbarian_movement_blockout.png` (444 KB) — 8-direction sheet
  - `barbarian_movement_blockout.manifest.json` — engine source of truth
  - `barbarian_movement_blockout.manifest.spec.json` — forward-looking spec
  - `barbarian_movement_blockout_preview.png` — labeled dev view
- **Goblin** (enemy character — seed `30_001`, added 2026-04-20):
  - `goblin_movement_blockout.png` (488 KB) — 8-direction sheet
  - `goblin_movement_blockout.manifest.json`
  - `goblin_movement_blockout.manifest.spec.json`
  - `goblin_movement_blockout_preview.png`

Two characters now live in this workflow's library. Scaffolds can drop
in either (or both) without re-establishing identity — each has its own
seed-pinned description that the workflow's prompt template fills out
per direction.

**Adding a new character** is structurally identical to the barbarian /
goblin process:
1. Pick a new seed (convention: hero 2xxxx, enemy 3xxxx, NPC 4xxxx)
2. Write a character-description string and a movement-pose-description
3. Run 8 ERNIE calls via the 3-ERNIE pool (~25-50 s wall-clock)
4. Call `postprocess.assemble_movement_loop_blockout(direction_to_frame,
   ISO_LIB, character_id="<name>")`

The library grows without re-reading the prompt_template or rewriting
the pipeline.

## Findings from the canary round

### Identity preservation is strong with shared seed + fixed character description

Same lesson as `dialogue_portrait`: pin seed, keep character description
constant, vary only the direction description → character identity
holds across all 8 frames. Red braided beard, chainmail, leather pants,
axe-on-back all stable. This validates the blockout-first discipline —
the mid-stride pose can be treated as "the character" for prototyping
before animation budget is spent.

### Direction fidelity varies by angle

- **Full profiles (E, W):** rendered perfectly — clean side silhouettes.
- **3/4 back angles (NE, NW):** landed well — shows rear-shoulder pauldron.
- **3/4 front angles (SE, SW):** landed well — shows front chest detail.
- **Cardinal back (N):** rendered cleanly — back of head, axe prominent.
- **Cardinal front (S):** rendered but with residual-magenta foot shadow
  (the familiar chromakey caveat). Could be mitigated by regenerating
  with a fresh seed, but we ship the shadowed version to be honest
  about the failure mode.

### GPU-compute-bound at 1024 px

3-ERNIE parallel dispatch at 1024 px gives ~1.4× speedup, confirming
the earlier finding that the RTX PRO 6000 saturates at 1024 px. The
pool benefit is real but modest for character-scale work.

For the next iso character (or the full animation phase), the pool's
value is: **reduced queue latency** (multiple characters can gen in
parallel) rather than reduced per-character wall-clock.

### Prompt engineering for direction

"Isometric" alone doesn't land — the model often renders
orthographic-ish or pure profile. Adding the literal number
`26.57 degree camera elevation angle` and direction-specific cues like
`facing up-and-right toward the upper-right corner` reliably produces
the right angle. Direction descriptions should spell out BOTH the
heading AND the visible-body-angle cue ("three-quarter back angle",
"full profile", "three-quarter front angle") for best results.

### Future animation hook is the point

The `anim_frame_targets` metadata in `blockout.spec.json` is the
contract between this workflow and the future `character_animation`
workflow. That workflow will consume this spec + the blockout frames
and fill in the full 320-frame animation without needing to re-derive
the character's identity (the seed + description are already captured
in the manifest).

This is the **coverage over categories** pattern: one character
workflow now serves as the foundation for ~3 downstream workflows
(animation, rotation, palette variants) without re-running the
identity-establishment work.
