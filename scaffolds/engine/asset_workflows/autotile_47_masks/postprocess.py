"""autotile_47_masks: algorithmic Wang 47-tile mask generator + terrain
compositor.

The 47 valid masks come from enumerating the 2^8 = 256 combinations of
the 8 neighbors (N/NE/E/SE/S/SW/W/NW each match-or-not), then collapsing
under the **corner-dependency rule**: a corner neighbor only contributes
a visible shape IF both of its adjacent edges are also "match." This
rule reduces the 256 raw combinations to exactly 47 distinct shapes.

ERNIE is NOT used anywhere in this pipeline — the masks are precise
geometric shapes that the diffusion model renders poorly. Algorithmic
drawing (PIL) is reliable and exact.

Mask convention:
- Each mask is a 128×128 **alpha mask** (single channel).
- White (255) = this pixel shows the CENTER tile's terrain.
- Black (0) = this pixel shows the NEIGHBOR's terrain.
- The mask's 4 corners are "eaten" (shown as neighbor) when the
  corresponding neighbor corner/edges don't match.
- Geometry: each mask is divided into a 4×4 grid of 32-px cells. The 4
  inner cells are always opaque. Edge cells open (neighbor shows) when
  the corresponding edge neighbor doesn't match. Corner cells open when
  the corner bit is cleared (after dependency normalization).

Compositing (`composite_tile`):
  center_tile = PIL RGB, 128×128
  neighbor_tile = PIL RGB, 128×128
  mask = PIL L, 128×128 (the Wang mask for a given bitmask)
  → Image.composite(center_tile, neighbor_tile, mask) = blended tile
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

# Neighbor bit positions (standard clockwise-from-north).
N, NE, E, SE, S, SW, W, NW = 1, 2, 4, 8, 16, 32, 64, 128


def normalize_bitmask(b: int) -> int:
    """Apply the Wang corner-dependency rule and return the canonical form.

    A corner bit is only meaningful if BOTH its adjacent edge bits are set.
    """
    if (b & NE) and not ((b & N) and (b & E)):
        b &= ~NE
    if (b & SE) and not ((b & S) and (b & E)):
        b &= ~SE
    if (b & SW) and not ((b & S) and (b & W)):
        b &= ~SW
    if (b & NW) and not ((b & N) and (b & W)):
        b &= ~NW
    return b


def enumerate_valid_bitmasks() -> list[int]:
    """Return the 47 canonical Wang bitmasks, sorted."""
    valid = set()
    for b in range(256):
        valid.add(normalize_bitmask(b))
    return sorted(valid)


@dataclass(frozen=True)
class MaskSpec:
    tile_px: int = 128
    grid: int = 4  # 4×4 subgrid; inner 2×2 always opaque, outer ring conditional


def draw_mask(bitmask: int, spec: MaskSpec = MaskSpec()) -> Image.Image:
    """Render the alpha mask for a given Wang bitmask.

    Geometry (4×4 cell grid on a 128×128 canvas = 32-px cells):

      [NW] [N ] [N ] [NE]
      [W ] [·C] [C·] [E ]
      [W ] [·C] [C·] [E ]
      [SW] [S ] [S ] [SE]

    - Center (C cells, indices (1,1)-(2,2)): always opaque.
    - Edge strips (N, E, S, W middle cells): opaque if edge bit set.
    - Corners (NW, NE, SW, SE single cells): opaque if corner bit set
      (after dependency normalization).
    """
    b = normalize_bitmask(bitmask)
    tile = spec.tile_px
    cell = tile // spec.grid
    img = Image.new("L", (tile, tile), 0)
    d = ImageDraw.Draw(img)

    # 1. Inner 2x2 always opaque
    d.rectangle([cell, cell, 3 * cell - 1, 3 * cell - 1], fill=255)

    # 2. Edges — each is a 2-cell strip on one side.
    if b & N:
        d.rectangle([cell, 0, 3 * cell - 1, cell - 1], fill=255)
    if b & S:
        d.rectangle([cell, 3 * cell, 3 * cell - 1, 4 * cell - 1], fill=255)
    if b & W:
        d.rectangle([0, cell, cell - 1, 3 * cell - 1], fill=255)
    if b & E:
        d.rectangle([3 * cell, cell, 4 * cell - 1, 3 * cell - 1], fill=255)

    # 3. Corners — single cells.
    if b & NW:
        d.rectangle([0, 0, cell - 1, cell - 1], fill=255)
    if b & NE:
        d.rectangle([3 * cell, 0, 4 * cell - 1, cell - 1], fill=255)
    if b & SW:
        d.rectangle([0, 3 * cell, cell - 1, 4 * cell - 1], fill=255)
    if b & SE:
        d.rectangle([3 * cell, 3 * cell, 4 * cell - 1, 4 * cell - 1], fill=255)

    return img


def write_all_masks(out_dir: Path, spec: MaskSpec = MaskSpec()) -> list[Path]:
    """Render and save all 47 canonical masks to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for b in enumerate_valid_bitmasks():
        mask = draw_mask(b, spec)
        p = out_dir / f"mask_{b:03d}.png"
        mask.save(p, format="PNG", optimize=True)
        paths.append(p)
    return paths


def composite_tile(
    center_tile: Image.Image,
    neighbor_tile: Image.Image,
    mask: Image.Image,
) -> Image.Image:
    """Blend center and neighbor terrain tiles using the alpha mask."""
    c = center_tile.convert("RGB")
    n = neighbor_tile.convert("RGB")
    m = mask.convert("L")
    # Ensure all three are same size
    target = m.size
    if c.size != target:
        c = c.resize(target, Image.NEAREST)
    if n.size != target:
        n = n.resize(target, Image.NEAREST)
    return Image.composite(c, n, m)


def composite_full_set(
    center_tile_path: Path,
    neighbor_tile_path: Path,
    masks_dir: Path,
    out_dir: Path,
) -> list[Path]:
    """Produce all 47 composite tiles from center + neighbor inputs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    center = Image.open(center_tile_path).convert("RGB")
    neighbor = Image.open(neighbor_tile_path).convert("RGB")
    paths: list[Path] = []
    for b in enumerate_valid_bitmasks():
        mask_path = masks_dir / f"mask_{b:03d}.png"
        if not mask_path.exists():
            continue
        mask = Image.open(mask_path).convert("L")
        tile = composite_tile(center, neighbor, mask)
        p = out_dir / f"tile_{b:03d}.png"
        tile.save(p, format="PNG", optimize=True)
        paths.append(p)
    return paths


def assemble_catalog_sheet(tile_paths: Iterable[Path], out_path: Path, cols: int = 8) -> Path:
    """Tile the produced masks/composites into one preview sheet."""
    tile_paths = list(tile_paths)
    if not tile_paths:
        raise ValueError("no tiles to assemble")
    first = Image.open(tile_paths[0])
    tile_w, tile_h = first.size
    rows = (len(tile_paths) + cols - 1) // cols
    mode = first.mode
    canvas = Image.new(mode, (cols * tile_w, rows * tile_h), 0 if mode == "L" else (40, 40, 40))
    for i, p in enumerate(tile_paths):
        im = Image.open(p)
        col, row = i % cols, i // cols
        canvas.paste(im, (col * tile_w, row * tile_h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG", optimize=True)
    return out_path


def to_thumbnail(src: Path, dst: Path, max_px: int = 256, max_bytes: int = 48_000) -> Path:
    img = Image.open(src).convert("RGBA")
    side = max_px
    while True:
        w, h = img.size
        scale = min(side / max(w, h), 1.0)
        tw, th = max(1, int(w * scale)), max(1, int(h * scale))
        thumb = img.resize((tw, th), Image.NEAREST) if scale < 1 else img
        dst.parent.mkdir(parents=True, exist_ok=True)
        thumb.save(dst, format="PNG", optimize=True)
        if dst.stat().st_size <= max_bytes or side <= 32:
            return dst
        side //= 2
