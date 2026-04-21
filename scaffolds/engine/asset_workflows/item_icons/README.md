# item_icons

**Flag:** STATIC
**Projection:** 3/4 front-facing product shot (centered icon)
**Covers Shoal plan categories:** 39 (weapons), 40 (consumables), 41 (equipment/armor)
**Consumer scaffolds:** every scaffold with an inventory or pickup UI

Unified STATIC workflow covering three item categories — weapons,
consumables, equipment — with one shared prompt template and per-category
defaults in `anim_set.json`. Single-call generation per icon; full
23-icon baseline library ships in ~3 min single-pipe, ~90s with 3-way
parallel pool.

## Pick this over a per-scaffold custom icon when…

- The item is one of the 23 canonical baseline subjects, or a near
  relative (template is open-vocabulary on `<subject_description>`).
- The target is a UI inventory slot at 128 px (consumable) or 256 px
  (weapon / equipment).
- The aesthetic is open to one of the named style_variant defaults
  (Diablo / Stardew / Hollow Knight / Zelda). Strict custom aesthetics
  may need a scaffold-specific override.

## Pipeline (one ERNIE call per icon)

1. Look up `anim_set.json::categories.<category>.subjects.<subject>` →
   `{seed_offset, desc}`. Full seed = `category.seed_base + seed_offset`.
2. Fill `prompt_template.md` placeholders and hit ERNIE
   `/v1/workflows/icon` at 512×512.
3. `postprocess.crop_to_icon(src, out_dir, pad_px=20, out_px=<category.out_px>)`
   — tight alpha-bbox crop, pad-to-square, LANCZOS downscale.

## ERNIE call count budget

- **Full baseline library:** 23 icons = 23 calls / ~3 min single-pipe.
- **With 3-way parallel pool:** ~90 s (parallel at 512 px gives a stronger
  speedup than at 1024 px — observed 4× effective at 3 parallel jobs,
  ~1.4× at 9 parallel jobs as the GPU saturates).
- **Canary round:** 3 icons (one per category) — ~4 s wall-clock.

## Canary corpus

Three canaries (see `canary_prompts.jsonl`):

- `canary_001_weapon_sword.png` — Diablo-II painterly longsword
- `canary_002_consumable_potion_red.png` — Stardew-style red healing potion
- `canary_003_equipment_helmet.png` — Hollow-Knight-style knight helmet

All three rendered cleanly in 4 s wall-clock via the 3-ERNIE pool
(~4× speedup vs single-pipe at 512 px). Chromakey was clean on all 3 —
items are compact silhouettes with no magenta-adjacent shadows.

## Library seeds

`scaffolds/engine/asset_library/item_icons/`:
- `baseline_weapon_sword.png` (30 KB) — Diablo longsword
- `baseline_consumable_potion.png` (36 KB) — Stardew red potion
- `baseline_equipment_helmet.png` (17 KB) — Hollow Knight helmet

These seeds prove the per-category pattern works and serve as style
anchors for `edit_image` variations (swap grip color, swap potion hue,
swap helmet plume).

## Known caveats

### 3/4 front-facing angle is the sweet spot

Pure-profile icons lose detail at icon scale (side view of a sword is
just a line). Pure-front icons lose subject-readability (front view of a
sword is a small square). **3/4 angle** balances both and is the
template's default — named "product shot" because the model understands
that as centered-subject, clean studio lighting. Overriding to pure
profile or pure front works but expect lower silhouette readability.

### Style-variant fidelity varies by aesthetic

Canary findings:
- **Diablo II painterly:** landed nearly perfectly — dark fantasy,
  weathered textures, deep shadows.
- **Stardew Valley warm cartoon:** landed well — saturated colors, clean
  cel-shading, glass highlights, minor pixel-art undertone.
- **Hollow Knight inky monochrome:** landed as "stylized with bold
  outlines" but NOT strictly monochrome (the canary 3 helmet has silver
  + gold + red, not the near-B/W palette Hollow Knight uses). For strict
  Hollow Knight monochrome, run `normalize_palette(dst, max_colors=6)`
  post-gen, biasing toward a bw+accent palette.

### Generating at 512 px then downscaling gives sharper icons

At 256 px target size, generating at 256 directly produces blurry,
low-detail icons (the model has less pixel budget to render craft
details like sword engravings). Generating at 512 and LANCZOS-downscaling
to 256 gives cleaner output. Same principle for consumables at 128 px —
always gen at 512, downscale after.

### Copyright-prior warning (unchanged)

Icons don't summon copyrighted characters (they're items, not
characters), but they DO auto-reconstruct iconic game assets — the
Triforce, the Master Sword, a Pokeball, etc. Include pattern-breaking
details in `<subject_description>` for any icon whose generic
description overlaps a famous item.

### `keep_largest_only=True` is the right default

Icons are compact single-subject silhouettes. Opposite of the spike-VFX
caveat in `vfx_library`; here the default is correct. Don't flip it
unless you're doing an item-cluster icon (e.g., coin pile with multiple
disconnected coins).

### Future work — full 23-icon batch build

This canary round ships the pipeline + 3 reference icons; the full
23-icon baseline library build (8 weapons + 8 consumables + 7 equipment)
is a dedicated round. Live at `~/shoal_scratch/notes/build_item_icons_full.py`
(not yet written) when that round runs.
