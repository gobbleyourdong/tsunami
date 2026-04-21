# autotile_47_masks — NOT an ERNIE workflow

**This workflow does NOT use ERNIE at any stage.** The 47 Wang masks are
precise geometric shapes; the diffusion model renders those unreliably.
Algorithmic drawing with `PIL.ImageDraw` is exact, fast (~50 ms total
for all 47), and reproducible.

## What the workflow produces

- **47 alpha masks** at 128×128, one per canonical Wang bitmask, shipped
  in `scaffolds/engine/asset_library/autotile_masks/mask_<bitmask>.png`.
- **A compositor** (`postprocess.composite_full_set`) that takes two
  terrain tiles (center + neighbor, e.g. from the `tileable_terrain`
  workflow library) and produces all 47 Wang variants by alpha-blending
  center over neighbor through each mask.
- **Canary composites** (grass center × stone neighbor) that prove the
  compositor produces visually-correct transitions for three canonical
  bitmasks: full-match, isolated, and edge-NES.

## Input signature (for the compositor, not ERNIE)

| Input | Meaning |
|---|---|
| `center_tile` | the terrain that fills the tile's center — e.g. `grass_128.png` from `tileable_terrain/` library |
| `neighbor_tile` | the terrain that fills edges/corners where the neighbor doesn't match — e.g. `stone_128.png` |
| `mask` | one of the 47 pre-rendered masks; selected by bitmask value |

## Why the 47 and not 16 or 256?

- **16-tile minimal** (N/E/S/W each match-or-not): only handles flat
  edges. Corners are always "dictated by adjacent edges" — which means
  diagonally-adjacent same-terrain tiles don't get the inside-corner
  shape they should. Blocky, looks wrong.
- **256-tile raw** (all 8 neighbors independent): over-specified. Most
  combinations are redundant under the corner-dependency rule — a
  corner can only contribute to the shape if both its adjacent edges
  match, so un-supported corner bits produce the same visible tile as
  their cleared-corner counterparts.
- **47-tile canonical** (8 neighbors, corner-dependency normalized):
  the minimal set that covers all visually-distinct shapes. Standard
  convention in Godot autotile, GameMaker, RPG Maker VX/MZ, Tiled.

## Usage (from a scaffold)

```python
from scaffolds.engine.asset_workflows.autotile_47_masks.postprocess import (
    composite_full_set, enumerate_valid_bitmasks, composite_tile,
)
from pathlib import Path

MASKS = Path("scaffolds/engine/asset_library/autotile_masks")
TERR = Path("scaffolds/engine/asset_library/tileable_terrain")

# Batch: produce all 47 tiles for a (grass, stone) pair
out = Path("my_scaffold/assets/tiles/grass_on_stone/")
composite_full_set(TERR / "grass_128.png", TERR / "stone_128.png", MASKS, out)
# Now out/ has tile_000.png, tile_001.png, … tile_255.png (47 of them).

# Runtime: given a tile's neighborhood bitmask, look up the right sprite
from PIL import Image
def lookup_autotile(bitmask, center_path, neighbor_path):
    from scaffolds.engine.asset_workflows.autotile_47_masks.postprocess \
        import normalize_bitmask, draw_mask, composite_tile
    b = normalize_bitmask(bitmask)
    mask = Image.open(MASKS / f"mask_{b:03d}.png")
    return composite_tile(Image.open(center_path), Image.open(neighbor_path), mask)
```

## No ERNIE prompt template here

Because this workflow is algorithmic, there is no `<placeholder>` prompt
and no `/v1/workflows/icon` call. The "canary prompts" file describes
the bitmask combinations we render for verification, not text prompts
for a diffusion model.
