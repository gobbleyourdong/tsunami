# tree_static

**Flag:** STATIC (optional-anim `wind_sway` variant declared but not
bundled by default)
**Projection:** multi — `top_down` orthographic overhead + `iso_side` 3/4
**Coral gap:** `asset_tree_static_base_001` + `asset_tree_static_001`
**Consumer scaffolds:** any outdoor map scaffold (most gamedev, most
infra diagrams that include landscape)

Single-tree sprites, 5 species × 2 projections = 10 baseline sprites.
Static by design — wind sway should be a runtime CSS/shader transform
rather than a baked frame sequence.

## Pick this over a per-scaffold custom tree when…

- The tree is one of the 5 canonical species (`oak`, `pine`, `palm`,
  `dead`, `cherry_blossom`) or a near-relative (the open-vocabulary
  `<species>` placeholder accepts any tree description).
- The target projection is top-down or 3/4 iso. Pure side-view for a
  platformer parallax layer is a different workflow (not yet shipped —
  side-view trees want a tall aspect ratio and richer trunk detail).

## Pipeline (one call per species × projection)

1. Caller iterates `anim_set.json::species` entries.
2. For each (species, projection) pair:
   - fill `prompt_template.md`'s `<species>`, `<projection_phrase>`,
     `<species_palette>`, `<style_modifiers>`
   - hit ERNIE `/v1/workflows/icon` with `seed =
     species.seeds[projection]`, `mode=icon`,
     `overrides.keep_largest_only=True` (trees are compact silhouettes)
3. `postprocess.crop_and_resize(src, out_dir, pad_px=16, out_height=288)`
   — alpha-crop, preserve aspect, resize to scaffold target.

## ERNIE call count budget

- Full catalog (5 species × 2 projections): **10 calls** / ~1.5 min
- Priority-1 only (oak / pine / palm × 2 projections): **6 calls** / ~1 min

## Canary corpus

Three canaries (see `canary_prompts.jsonl`):

- `canary_001_oak_iso_side.png` — mature oak in 3/4 view, painterly
- `canary_002_pine_top_down.png` — pine (rendered as side-view; see caveat)
- `canary_003_cherry_blossom_iso_side.png` — cherry blossom 3/4

## Library seeds

`scaffolds/engine/asset_library/tree_static/`:
- `baseline_oak_iso.png` — 3/4 oak, highest fidelity canary
- `baseline_cherry_blossom_iso.png` — 3/4 cherry blossom, pixel-art nudge

## Known caveats (from the canary corpus)

### Top-down orthographic is still fighting us

Same lesson as `top_down_character` workflow #1 round: asking for
"orthographic top-down overhead view, seen directly from above" produces
a side-profile render ~30% of the time. Canary 002 (pine top-down)
landed as a full side view of a pine despite the explicit geometry
phrase.

**Mitigation ladder:**

1. Bump the prompt with `viewed from directly above looking straight
   down, camera pointing at the ground`. (Already in the template.)
2. Add `circular canopy silhouette, no visible trunk sides, trunk is a
   small dot at the center of the canopy`. Geometry-literal phrases
   work where style labels don't.
3. Regenerate with a different seed; 1 in 3 attempts typically lands.
4. **Accept the side view.** For top-down tile games, a side-view tree
   sprite renders fine as a "tall object billboard" — the engine z-sorts
   it against the character and the composition reads correctly.

The `baseline_pine_top_down.png` library seed is intentionally NOT
shipped (canary 002 is in the workflow dir as a thumbnail for
documentation; it is not a seed). Re-run with mitigation 1+2 before
promoting to the library.

### `style_modifiers` nudges, doesn't clamp

Canary 003 asked for `pixel-art with visible pixels and limited
palette`; ERNIE rendered a semi-painterly cherry blossom with pixel-art
hints but not strict pixel-art. Same issue as every workflow where
style is prompted rather than post-processed. For strict retro look run
`normalize_palette(dst, max_colors=16)` on the output.

### Trees have compact silhouettes — `keep_largest_only=True` is correct

Unlike VFX (see vfx_library caveats), trees are single connected
subjects. `keep_largest_only=True` is the right default and should
remain so. No interior magenta pockets to worry about.

### No baked shadow — engines handle it

Per the consistent finding across workflows, the template does NOT ask
for a ground shadow. Engines should drop an elliptical shadow under the
tree sprite at render time. Saves both ERNIE call budget and avoids
purple-ellipse chromakey residual.
