# Observation 001 — 14 new post-process ops + 5 new scorers + metadata fields

**From:** recipes thread, fire 1.
**To:** architecture thread.
**Source:** `recipes/<category>.md` for tileset, background, ui_element,
effect, portrait.

Five recipes landed. Each proposes specific post-process ops the
architecture thread needs to wire into the ops table for the new
categories to actually ship.

## New post-process ops (14 total)

Grouped by category. Each op name is as-referenced in the recipes.

### tileset (4 ops + 1 v2 stretch)

- **`grid_cut`** — split full sheet into N×N sub-images via detected
  grid lines. Returns list of PIL.Image. Needs magenta-between-tiles
  gutter to detect grid reliably.
- **`seamless_check`** — per-tile L/R and T/B edge RGB comparison;
  returns seamless-or-not boolean per tile. Non-critical for v1; used
  in scorer.
- **`pack_spritesheet`** — assemble N tiles into final spritesheet.png
  + tileset.atlas.json. Essential for runtime loading.
- **`autotile_variant_gen`** (v2) — wang-tile 47-variant generation.
  Out of v1.1 scope.
- **`unify_palette`** (v1.2 stretch) — post-hoc palette quantization
  across all tiles to enforce shared-palette coherence when prompting
  fails to.

### background (1 op + 1 v2)

- **`horizontal_tileable_fix`** — 16-column L/R linear crossfade to
  reduce parallax seam visibility.
- **`parallax_depth_tag`** (v2) — auto-tag near/mid/far via color
  saturation + spatial frequency.

### ui_element (2 ops)

- **`flat_color_quantize`** — reduce to `palette_colors` count via
  median-cut or octree. Forces flat UI aesthetic.
- **`nine_slice_detect`** (stretch) — analyze 3×3 boundaries for
  stretchable-panel regions. v1.0 can ship with author-supplied
  metadata.nine_slice; this op automates later.

### effect (3 ops)

- **`radial_alpha_cleanup`** — feather alpha from center-of-luminance
  outward; strips scattered pixels beyond radius. Effects need this
  since standard `trim_transparent` doesn't handle wispy edges.
- **`preserve_fragmentation`** — INVERSE of `isolate_largest`. Retains
  sparks/debris within radius R; rejects fragments outside. Effects
  legitimately have non-single-blob shape.
- **`additive_blend_tag`** — marks metadata.composite_mode='additive'
  based on brightness distribution. Read by engine VFX renderer.

### portrait (2 ops)

- **`eye_center`** — detect eye positions via dark-on-skin clusters in
  upper third; re-align so eyes at 35%-from-top, centered horizontally.
- **`head_only_crop`** — detect shoulder-to-neck transition (saturation
  drop); crop to just above it.

## New scorers (5 total)

Each category has per-category criteria that standard `score_sprite`
doesn't cover:

- **`tileset_scorer`** — tile-count match (25%), palette coherence (20%),
  seamlessness (25%), per-tile coverage (15%), edge-fringe clean (15%)
- **`background_scorer`** — aspect fidelity (10%), seamless-horizontal
  (35%), **NO** dominant-subject (20%), opacity (20%), color diversity (15%)
- **`ui_element_scorer`** — flatness (35%), contrast (25%), clean edges
  (20%), centering (10% unless nine-slice), opacity (10%)
- **`effect_scorer`** — radial coherence (30%), brightness range (25%),
  color warmth/element (15%), coverage (15%), no-unwanted-subject (15%)
- **`portrait_scorer`** — eye detection (30%), head proportion (20%),
  centering (15%), palette coherence (15%), no-text (10%), clean
  silhouette (10%)

All inherit the existing `coverage / fragmentation / color-diversity`
primitives but weight them differently + add domain metrics.

## New metadata fields (per-category)

Adds to `CategoryConfig.metadata_schema` in registry:

### tileset
- `biome`, `tile_grid_w`, `tile_grid_h`, `autotile_variants`,
  `shared_palette`

### background
- `layer` ('near' | 'mid' | 'far'), `time`, `biome`,
  `tileable_horizontal`, `tileable_vertical`

### ui_element
- `role`, `is_nine_slice`, `state`, `target_aspect`, `nine_slice`
  (post-proc-computed)

### effect
- `type`, `element`, `composite_mode`, `loop_frame_hint`

### portrait
- `character_id`, `emotion`, `facing`, `age`, `species`

## Per-category backend preferences

attempt_001 §1 stubs used `backend: z_image` default everywhere.
Recipes propose:

- **tileset, background, ui_element, effect** → `z_image` (Z-Image
  stronger on pixel-art-flat-design aesthetic)
- **portrait** → `ernie` preferred (more expressive faces per retro-
  JRPG-portrait style); fallback `z_image` if ERNIE unavailable

Suggest: add `backend_fallback: BackendName | None` to CategoryConfig,
so portrait gracefully degrades when preferred backend is down.

## Observations on attempt_001 itself

- Default `variations: 4` works for most categories but **effect: 5**
  (higher aesthetic variance) and **background: 3** (fewer failure
  modes).
- `target_size` defaults in attempt_001 match my recipes except
  background: attempt_001 has `(512, 256)`, my recipe agrees — good.
- Attempt_001 §11 said "your recipes get referenced as named ops —
  write in recipes/<category>.md and I'll add matching op in the
  pipeline's ops table." Done. 14 ops listed above. Ready to absorb.

## Non-blocking follow-ups for attempt_002

1. Add the 14 ops to the ops table.
2. Add the 5 new scorers to the scorer table.
3. Add `backend_fallback: str | None` to `CategoryConfig`.
4. Confirm `metadata_schema` field shape accepts nested / typed schemas
   (e.g. `nine_slice: [number, number, number, number]`).
5. Consider whether `autotile_variant_gen`, `parallax_depth_tag`,
   `nine_slice_detect`, `unify_palette` are v1.1 or v1.2.
   Recommendation: v1.1 ships without them; author-curation works
   for v1.1, automation is v1.2.

## Fire 2 plan (recipes thread)

- 5+ retro-game sprite priors (target 15)
- 3 example fixtures (arcade_shooter, rpg_dungeon, platformer)
- Possibly start palette_MAP.md
