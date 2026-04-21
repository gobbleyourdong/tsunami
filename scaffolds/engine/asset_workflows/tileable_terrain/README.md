# tileable_terrain

**Flag:** STATIC (tileable)
**Projection:** orthographic top-down
**Coral gap:** `asset_tileable_terrain_001`
**Consumer scaffolds:** every tile-based scaffold (`scaffolds/gamedev/action_adventure`,
`jrpg`, `platformer`, most `infra/` that render a map)

Seamless tileable ground textures generated one-shot from ERNIE-Image-Turbo
`mode=photo`, post-sampled into engine-sized 64×64 or 128×128 tile PNGs.

## Pick this over siblings when…

- You need a uniform ground texture (grass, stone, sand, water, snow, etc.)
- The target is a 2D tile layer (any projection — works for top-down and
  isometric as long as the engine takes a single repeating tile image).
- You're fine with manual seam inspection; no automated tileability gate
  is reliable enough to block on.

## Pipeline (one ERNIE call per material)

1. Caller fills `prompt_template.md`'s `<material>` + `<style_modifiers>`
   and hits ERNIE `/v1/images/generate` (note: `/generate`, not
   `/workflows/icon` — there's nothing to chromakey in a photo texture).
   **Seed is pinned per-material in `anim_set.json::materials.*.seed`**
   so re-runs are reproducible.
2. ERNIE returns a 1024×1024 RGB texture field.
3. `postprocess.sample_tile_center(field, tile_px=128, seam_pad_px=16)`
   crops the geometric center of the field (maximum distance from
   composition-biased edges). Returns a 160×160 RGBA patch.
4. Caller optionally `postprocess.feather_edges(patch, feather_px=16)` if
   the engine supports alpha-blended tile wrapping (skip if it's hard-edge
   tiling).
5. Exact-crop to `tile_px` and save as the final RGB tile.
6. `postprocess.verify_tileable(tile, out_path)` writes a 3×3 wrap grid
   for manual inspection.

## ERNIE call count budget

Per `anim_set.json::ernie_call_count.total`: **12 calls** for the full
baseline library (9 priority-1 every-scaffold materials + 3 priority-2
biome-specific). At ~9 s / Turbo call that's ~2 min of ERNIE wall-clock
for a full set.

## Canary corpus

Three canaries in this directory (see `canary_prompts.jsonl`):

- `canary_001_grass.png` — dense green grass blades, saturated cartoon
- `canary_002_stone.png` — mossy gray flagstone pavement, photoreal
- `canary_003_water.png` — shallow rippling clear freshwater, cyan-teal

Each is a 192-px PNG ≤ 24 KB (photoreal textures compress poorly, so the
thumb ceiling is lower than the 50 KB budget — still well under cap).
Full-res 1024×1024 sources live in `workspace/asset_gen/tileable_terrain/`
(gitignored).

## Library seed

`scaffolds/engine/asset_library/tileable_terrain/` ships:

- `grass_128.png`, `stone_128.png`, `water_128.png` — 128×128 RGB tile
  samples, center-extracted from the canary fields.
- `grass_wrap_proof.png`, `stone_wrap_proof.png`, `water_wrap_proof.png` —
  3×3 wrap proofs that show exactly how each tile seams against itself.

Scaffolds that need any of the three baseline materials can pull the
`*_128.png` directly — it's already sampled and seam-tested.

## Known caveats (from the canary corpus)

### Tileability is NOT guaranteed — inspect the wrap proof

**canary_003_water failed the wrap-grid eye test.** Each tile has a slight
color/tone mismatch at the edges that reads as a grid pattern when
repeated. The center-sample approach works for textures with high local
uniformity (grass, stone, sand, dirt, moss) but fails for textures with
large-scale brightness/hue gradients (water with caustic highlights,
lava with molten-core variation, some snow with sun-dappling).

**Mitigation ladder, cheapest first:**

1. **Regenerate with a different seed.** Seeds are pinned for
   reproducibility, but if the pin produced a bad tile, overwrite the
   seed in `anim_set.json::materials[name].seed` and regenerate. Record
   the new pin.
2. **Add tighter style modifiers.** `uniform flat lighting, no bright
   highlights, no dark patches` pushes the model toward more-uniform
   output, often tileable where the default wasn't.
3. **Offset-mirror blend** (future work — not shipped). Blend the center
   patch against a 50 %-offset mirror of itself, which moves seam
   artifacts to the interior where they average out.
4. **Accept the seam.** For water, lava, animated surfaces — if the
   engine layers a motion effect on top (shader ripples, caustic overlay
   sprite) the seam is invisible at runtime. Ship the tile and document
   the seam in the scaffold README.

### Do not feather with hard-edge engines

`postprocess.feather_edges` applies a radial-cosine alpha ramp on the
outer `feather_px` ring. This helps engines that do alpha-blended tile
wrapping. Engines that hard-edge tile (most 2D engines) will see the
feathered edge as a transparent border — **skip the feather step** and
exact-crop instead.

### mode=photo has no chromakey — do not pass `mode=icon`

The texture IS the content; there is no background to strip. Passing
`mode=icon` or calling `/v1/workflows/icon` produces undefined behavior
(the chromakey will eat random patches where magenta-adjacent colors
appear in the texture — bloody-lava turns half-transparent, mossy-stone
gets magenta-hole artifacts).

### The 12-material base set can be expanded per-scaffold

The shipped set covers most scaffolds. Add biome-specific materials
(`volcanic_rock`, `ice_shelf`, `cloud_surface`, `crystal_floor`,
`marble_tile`, `tentacle_flesh`, `tech_panel`, etc.) by adding entries to
`anim_set.json::materials` with pinned seeds and running the per-material
gen. Keep the prompt template the same; only `<material>` and
`<style_modifiers>` change.
