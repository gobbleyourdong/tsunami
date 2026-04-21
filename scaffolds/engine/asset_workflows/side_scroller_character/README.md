# side_scroller_character

**Flag:** ANIM
**Projection:** 2D side profile (pure left-facing baseline)
**Coral gap:** `asset_side_scroller_character_001`
**Consumer scaffolds:** `scaffolds/gamedev/platformer/` (and any future
fighting/stealth/metroidvania scaffolds that share 2D-profile character gen)

The canonical workflow for 2D platformer / action characters. Produces
per-frame pose PNGs from ERNIE-Image-Turbo mode=icon, stacks them into
horizontal strips per animation, and horizontal-flips for right-facing
where the character is left/right symmetric.

## Pick this over siblings when…

- You're in a 2D side-scrolling scaffold (platformer / action / stealth /
  metroidvania / fighting).
- You need the full platformer move-set (idle, walk, run, jump
  up/peak/down, land, attack light/heavy, hurt, death, wall-slide, dash,
  crouch, crouch-walk).
- Per-frame size target is **64×64 / 128×128 / 256×256**.
- The character's left/right silhouette is symmetric enough to mirror (or
  you're willing to disable `left_mirror_to_right` in `anim_set.json` and
  pay double the gen cost for handed designs).

## Pipeline (one call per frame, then stitch)

1. Caller iterates the `poses` array under each entry in
   `anim_set.json::anims` and fires one ERNIE call per pose:
   - fills `prompt_template.md`'s placeholders
   - hits ERNIE `/v1/workflows/icon` with `mode=icon`, `steps=8`,
     `cfg=1.0`, `1024×1024`
   - holds `seed` constant per `<character_name>` so identity stays
     stable across the whole 66-frame move-set
2. ERNIE returns a single-pose 1024×1024 RGBA PNG per call.
3. `postprocess.crop_and_resize(...)` tight-crops to the character's
   alpha bbox (+12 px padding), pads to square, and downscales to the
   target per-frame size.
4. `postprocess.stack_horizontal(frames, out_path)` concatenates the N
   per-frame PNGs for one anim into a horizontal strip.
5. If the scaffold needs right-facing frames,
   `postprocess.flip_for_right_facing(left_strip, right_strip)` mirrors
   the whole strip in one pass (cheaper than per-frame flipping).

## ERNIE call count budget

Per `anim_set.json::total_frame_budget.total`: **66 calls** for a full
move-set, left-facing only (right is a flip). At ~9 s / Turbo call that's
~10 min of ERNIE wall-clock per character on a single-pipeline pod; ~3.3
min if you're running 3 parallel pipelines with the round-robin chooser.

## Canary corpus

Three canary renders in this directory (see `canary_prompts.jsonl`):

- `canary_001_mario_idle.png` — platformer-hero idle, NES-style pixel art
- `canary_002_castlevania_walk_midstride.png` — gothic whip-hunter,
  mid-walk, painterly SOTN style
- `canary_003_celeste_dash.png` — crisp pixel-art sprinter, dash pose,
  Celeste-style

Each is a 256-px PNG ≤ 50 KB. Full-res production sheets land in
`workspace/asset_gen/side_scroller_character/` (gitignored).

## Library seeds

`scaffolds/engine/asset_library/side_scroller_character/`:
- `baseline_hunter.png` — original castlevania-walk-mid-stride reference
- **`barbarian_movement_blockout.png`** — 1-direction (left baseline) blockout
  of the cross-projection barbarian. **Same character appears in
  `iso_character/` and `top_down_character/` library slots** — one identity
  across 3 projections, ready for any side-scrolling scaffold to drop in.
- `barbarian_movement_blockout.manifest.json` — engine source of truth
- `barbarian_movement_blockout.manifest.spec.json` — forward metadata
  with `anim_frame_targets` for the full 15-anim platformer move-set
  (idle 6 / walk 8 / run 8 / jump phases / attacks / hurt / death / dash /
  crouch / wall-slide) that the future `character_animation` workflow
  will fill in.
- `barbarian_movement_blockout_preview.png` — labeled dev view

Right-facing frames are produced by horizontal-flipping the shipped
left-baseline frame — no separate gen needed.

## Postprocess retrofit (2026-04-20)

`postprocess.py` now imports from `_common/`:
- `_common.sprite_sheet_asm` — canonical sheet assembler
- `_common.character_blockout` — movement-loop blockout primitives

New entrypoint: `assemble_movement_loop_blockout(left_frame, out_dir,
character_id, cell_px)` — takes the single left-baseline frame and produces
the same sheet + manifest + spec format that `iso_character` and
`top_down_character` use. The future `character_animation` workflow consumes
all three uniformly.

## Known caveats (from the canary corpus — read this)

### The copyright prior auto-summons familiar silhouettes

Canary 001 prompted `red cap and blue overalls, wearing white gloves and
brown boots` — deliberately generic, deliberately no "M" in the prompt.
The output rendered a cap with a literal "M" logo anyway, because
`red-cap + blue-overalls + white-gloves` is the Nintendo archetype and
ERNIE's training data reconstructs the full pattern from any subset.

**Production hygiene:** every character description should include at
least one *distinguishing detail that breaks the pattern* — a green
scarf, non-white gloves, different boot color, a visible tattoo. Without
it, ~20% of prompts that accidentally hit a known silhouette will
auto-render the copyrighted version.

### Pose-description fidelity is ~70–80%

Canary 003 prompted `mid-dash body fully horizontal parallel to ground,
legs extended streamlined behind, arms pressed back`. ERNIE rendered a
beautiful mid-run pose instead — legs spread in running, not horizontal.
Where pose fidelity fails, it fails gracefully to an adjacent pose (run
instead of dash, swing instead of thrust, etc.), but the pose isn't
literally what you asked for.

**Mitigations:** name specific game references where the pose is iconic
(`Celeste Madeline dash pose, body rigid horizontal`) rather than
describing the geometry; or use `edit_image` to nudge a frame's pose
using a reference image from the library seed.

### Baked shadows survive extract_bg as purple blobs

Top-down canary 003 (drifter) and side-scroller canary 002 (walk) both
show dark purple ellipses under the character's feet — the requested
"soft ground shadow" gets drawn in magenta-adjacent dark purple, and
extract_bg's chromakey peel keeps it. **The template no longer requests
a baked shadow** (see `prompt_template.md`); engines should render
shadows at runtime. Override with `shadow_color: dark_slate_gray` if a
baked shadow is truly needed for a specific scaffold.

### Model palette sometimes drifts away from the requested style_variant

Canary 001 asked for `8-bit NES limited palette` and got 16-bit-ish
painterly work with a pixel-texture overlay. `style_variant` nudges, it
doesn't clamp. For strict retro palettes run the `normalize_palette`
postprocess with `max_colors=16` or `max_colors=4` for true 2-bit/NES.
