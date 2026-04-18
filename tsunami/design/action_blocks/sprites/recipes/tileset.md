# tileset — generation recipe

## Style prefix

```
pixel art tileset sheet, N×N grid of square tiles, each tile is a
distinct terrain type, tiles share a unified color palette, edges
seamless between neighbors, top-down 2D view, solid magenta #FF00FF
background between tiles, no characters, no shadows cast on tiles,
clean pixel edges, 16-bit style,
```

Notes:
- `N×N grid` gets templated per generation — the prompter fills
  "4x4" or "3x3" based on `metadata.tile_grid_w / tile_grid_h`.
- "between tiles" magenta gives pixel_extract + grid_cut a clean
  divider; Z-Image tends to put tile borders touching otherwise.

## Negative prompt

```
single tile, isolated, random colors, mismatched palette, 3d, perspective,
photo, realistic, blurry, soft, gradient, anti-aliased, text, labels,
numbers, border, frame, characters, animals, objects on tiles, shadows,
blurred edges between tiles, non-square tiles, trapezoid
```

Extra "non-square tiles" / "trapezoid" specifically because Z-Image
occasionally outputs isometric perspective even when asked for top-down.

## Default generation settings

- `gen_size: (1024, 1024)` — Z-Image-Turbo sweet spot; enough resolution
  to recover 4×4 or 6×6 grid cleanly
- `variations: 4` — best-of-N; tileset scoring is hard so more samples helps
- `target_size: (16, 16)` — PER TILE, not per sheet
- `palette_colors: 12` — small palette for NES/SNES/indie-retro feel
- `backend: z_image` — Z-Image produces more-faithful grid structure;
  ERNIE tends to stylize tiles into painting

## Post-processing chain

1. `pixel_extract` (existing) — magenta-keyed bg removal + grid recovery
   against the inter-tile magenta
2. **`grid_cut`** (new op; architecture thread to add) —
   split the full sheet into `N×N` sub-images based on detected grid
   lines. Output: list of PIL.Image, one per tile.
3. **`seamless_check`** (new op; architecture thread to add) —
   for each tile, test left-edge vs right-edge and top vs bottom. If
   they differ by more than threshold (RGB delta), mark as
   non-seamless. Returns dict `{ tile_id: is_seamless: bool }`.
4. `trim_transparent` per tile (existing)
5. `pixel_snap` per tile to `target_size` (existing)
6. **`autotile_variant_gen`** (new op; architecture thread to add,
   marked v2 if out of scope for first pass) — for tiles with
   `metadata.autotile_variants: '47'`, generate the 47 wang-tile
   variants algorithmically from the base tile + edge-masked neighbor
   patterns. v1 scope: skip (just ship base tiles).
7. **`pack_spritesheet`** (new op; architecture thread to add) —
   assemble the N tiles into a final sheet image + JSON tile atlas
   (coordinates). Stored as `tileset.png` + `tileset.atlas.json` in
   the asset record.

## Scorer

New scorer: `tileset_scorer`. Weighted criteria:
- **Tile count match** (1.0 if detected-tile-count == expected N×N; 0
  if off by >2) — 25% weight
- **Palette coherence** (all tiles share < 16 unique colors total) —
  20% weight
- **Seamlessness** (fraction of tiles that pass seamless_check) — 25%
  weight
- **Per-tile coverage** (each tile ≥ 80% opaque after grid-cut) — 15%
  weight
- **Edge fringe clean** (no magenta bleed on tile edges) — 15% weight

Does NOT use the existing centering or fragmentation metrics —
tilesets don't have a single centered subject.

## Example prompts (3+)

1. `pixel art grass tiles, overworld, 4x4 grid, green variations including dark grass, light grass, dirt path, flower patches`
2. `pixel art dungeon floor tiles, 3x3 grid, grey stone slabs, cracked variants, moss overgrown, arcane glyph`
3. `pixel art desert sand tiles, 4x4 grid, beige sand, dune shadows, rock outcrops, cactus base, dry riverbed, skull bleached`
4. `pixel art cave floor, 3x3 grid, dark stalactite drip, water puddle, mushroom patch, crystal embedded, torch mount`
5. `pixel art wooden floor tiles, 4x4 grid, planks varying stain, worn knot holes, rug, trapdoor`

## Metadata schema

```ts
{
  biome: 'overworld' | 'desert' | 'cave' | 'dungeon' | 'forest' | 'snow' | 'lava' | 'underwater' | 'city' | string,
  tile_grid_w: number,             // typical: 3 or 4 or 6
  tile_grid_h: number,
  autotile_variants: 'none' | 'basic' | '47' | 'blob',
  shared_palette: boolean,         // true = all tiles share 12-16 colors
}
```

`autotile_variants: 'none'` is v1 default. `'47'` is Godot / RPG Maker
style full-wang autotile set. `'blob'` is the 47-tile variant commonly
used in 2D platformers.

## Common failures + mitigations

1. **Z-Image bleeds tile edges together** → the magenta-between-tiles
   prompt token is load-bearing. If tiles still blend, increase sample
   count to 6 and pick best.
2. **Isometric perspective instead of top-down** → happens ~15% on
   dungeon/cave prompts. Explicit "top-down 2D view" + negative
   "isometric, perspective" mitigates but doesn't eliminate. Accept
   higher variations count or consider fallback to ERNIE for these.
3. **Tile count wrong** (asks for 4x4, gets 3x3 or 5x5) → grid_cut
   op should detect the actual grid and report. Manifest metadata is
   authorial intent; if actual differs, log + keep the sheet (still
   usable).
4. **One tile is a character** (unwanted sprite creeps into grid) →
   strong negative on "characters, animals, objects on tiles" +
   requires post-hoc manual review. Fix at recipe iteration time.
5. **Palette drift between tiles** (e.g. tile 1 is cool-blue-green,
   tile 2 is warm-yellow-green) — hard to eliminate via prompting.
   Post-process palette quantization over all tiles as a set (new op:
   `unify_palette` — architecture thread to add if failures persist).

## Handoff notes

- `grid_cut`, `seamless_check`, `pack_spritesheet` are new named ops.
  Architecture thread needs to add them to the ops table.
- `autotile_variant_gen` is v2 — out of scope for v1.1. Ship base
  tilesets first.
- `unify_palette` is a stretch-goal new op for post-hoc palette
  cleanup. Flag to synthesis as v1.2 candidate.
