# autotile_47_masks

**Flag:** STATIC (algorithmic — no animation, no ERNIE)
**Projection:** top-down tile
**Coral gap:** `asset_47_tile_autotile_masks_001`
**Consumer scaffolds:** any tile-map scaffold using Wang autotile
(Godot / GameMaker / Phaser / custom canvas tilemaps).

Produces a full 47-tile Wang-corner autotile set from any pair of
seamless terrain tiles (e.g. grass + stone) via 47 pre-rendered alpha
masks and a PIL-based compositor. **This workflow does NOT use ERNIE.**

## Pick this over hand-drawing autotiles when…

- You have 2+ seamless terrain samples from `tileable_terrain` (or any
  other source) and want programmatic transitions between them.
- The engine supports the canonical 47-tile Wang-corner bitmask lookup
  (Godot `auto_tile_coord`, GameMaker autotile, Tiled export, RPG
  Maker VX/MZ).

## Pipeline

### One-time setup (already shipped)

1. `postprocess.write_all_masks(asset_library/autotile_masks/)` — renders
   47 PNG masks at 128×128. Done at build time.

### Per-terrain-pair composite (run once per (center, neighbor) tile combo)

1. Pick any two tiles from `scaffolds/engine/asset_library/tileable_terrain/`
   (or any other 128×128 RGB sources).
2. `postprocess.composite_full_set(center, neighbor, mask_dir, out_dir)` →
   47 composites written as `tile_<bitmask>.png`.
3. At runtime, given a tile's neighborhood bitmask:
   - normalize via `postprocess.normalize_bitmask(b)`
   - look up `out_dir/tile_<normalized_b>.png`

## ERNIE call count budget

**Zero.** That's the whole point.

## Canary corpus

Three canaries (see `canary_prompts.jsonl`), each a composite of the
shipped `tileable_terrain/grass_128.png` over `stone_128.png` through a
specific Wang bitmask:

- `canary_001_full_match.png` (bitmask 255) — interior grass tile
- `canary_002_isolated.png` (bitmask 0) — grass island on stone field
- `canary_003_edge_nes.png` (bitmask 21) — grass meeting stone on the
  west edge

And a **preview sheet** of the full 47-tile catalog:

- `canary_catalog_sheet_grass_on_stone.png` — 8×6 grid showing all 47
  composites at once; quickest way to verify the mask geometry is
  correct end-to-end.

## Library seed

`scaffolds/engine/asset_library/autotile_masks/`:

- `mask_000.png` … `mask_255.png` — 47 alpha masks at 128×128 (only the
  47 canonical bitmask values have files; the other 209 values in
  [0, 255] normalize down to one of these 47)
- `_catalog_sheet.png` — 8×6 grid preview of all 47 masks in one image
  (2 KB, pure black/white)
- `_catalog_sheet_preview.png` — 512-px thumbnail of the same

Total library footprint: ~6 KB (masks compress beautifully — they're
rectilinear black-and-white).

## Bitmask convention

```
Bit positions (standard clockwise from north):
  N=1, NE=2, E=4, SE=8, S=16, SW=32, W=64, NW=128

Corner-dependency normalization:
  A corner bit is cleared unless BOTH adjacent edge bits are set.
  NE is cleared unless (N and E).
  SE is cleared unless (S and E).
  SW is cleared unless (S and W).
  NW is cleared unless (N and W).

Enumerating 0..255 and normalizing produces exactly 47 distinct values.
```

## Known caveats

### Mask geometry is rectilinear, not curved

The shipped masks are chunky — each tile is a 4×4 cell grid with the
center 2×2 always opaque, edges as 2-cell strips, corners as single
cells. This looks "pixel-art tilesheet" in style and plays nice with
NEAREST-neighbor scaling. It does NOT produce smooth curved transitions
like a hand-painted tileset would. For smooth transitions:

1. Swap `draw_mask` for a version using `ImageDraw.pieslice` / `arc`
   to round the corner bites. ~40 lines of additional math.
2. Apply a small Gaussian blur to the generated masks before compositing
   — softens the edge transitions at the cost of slightly-fuzzy seams.
3. Use `edit_image` on the chunky composites to smooth them (ERNIE can
   handle the smoothing step, it just can't draw the masks from scratch).

### Tile size is fixed at 128×128

Masks are rendered at 128×128 and the 4×4 cell grid (32 px cells)
assumes that size. For other tile sizes, override `MaskSpec.tile_px` at
`write_all_masks` time — cell size auto-scales, but the cell count
stays 4×4 so very small tiles (< 32 px) will have sub-pixel cells and
look crunchy.

### Compositor requires matching-size terrain inputs

`composite_tile` resizes mismatched inputs to the mask size with NEAREST
neighbor, which is fine for pixel-art but degrades photoreal terrain.
If your terrain tiles are 256×256 and you want high-resolution autotiles,
regenerate the masks at 256×256 (`write_all_masks(out_dir, MaskSpec(tile_px=256))`)
rather than relying on the compositor's auto-resize.

### 16-tile variant not shipped

The Shoal plan mentions a "16-tile minimal Wang set" (edges only, no
corner logic). That would be a subset of this workflow — just ignore
the corner bits and enumerate only the 16 edge-bitmask values. Not
shipped here because the 47-tile set supersedes it for almost all
production use. Add a helper in `postprocess.py` if a scaffold truly
needs the minimal set.
