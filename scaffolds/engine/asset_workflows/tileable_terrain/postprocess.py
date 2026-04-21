"""Postprocess for tileable_terrain workflow.

ERNIE-Image-Turbo with mode='photo' returns a 1024×1024 texture field. The
model does not know about tileability; seamlessness is produced by the
pipeline here:

  1. sample_tile_center(field, tile_px, seam_pad_px)
       - crop a (tile_px + 2*seam_pad_px)² patch from the exact geometric
         center of the field (maximum distance from composition bias at
         the edges).
  2. feather_edges(patch, feather_px)
       - radial-cosine alpha feather on the outer ring so the tile's own
         edges alpha-blend against a neighbor when the engine wraps them.
  3. verify_tileable(patch, out_path)
       - paste the patch 3×3 in a grid and write canary_wrap_<name>.png
         for the operator to eyeball. No automated seam metric is reliable.
  4. to_thumbnail(src, dst, max_px, max_bytes)
       - downscale + optimize for the canary slot.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def sample_tile_center(field_path: Path, tile_px: int, seam_pad_px: int = 16) -> Image.Image:
    """Crop a square patch centered on the field. Returns RGBA for alpha
    feathering compatibility (even though mode=photo inputs are RGB)."""
    img = Image.open(field_path).convert("RGBA")
    w, h = img.size
    side = tile_px + 2 * seam_pad_px
    if side > min(w, h):
        raise ValueError(f"field ({w}x{h}) too small for tile_px={tile_px} + seam_pad_px={seam_pad_px}")
    x0 = (w - side) // 2
    y0 = (h - side) // 2
    return img.crop((x0, y0, x0 + side, y0 + side))


def feather_edges(patch: Image.Image, feather_px: int = 16) -> Image.Image:
    """Radial-cosine alpha ramp on the outer `feather_px` ring.

    Engine consumers that do alpha-blended tile-edge-wrapping (e.g., when
    the tile is laid next to its own mirror for a seamless field) see a
    soft ramp instead of a hard edge. Engines doing hard-edge tiling will
    simply cap alpha to 255 — they won't see this.
    """
    if feather_px <= 0:
        return patch
    w, h = patch.size
    a = np.array(patch.split()[-1]).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    dx = np.minimum(xx, w - 1 - xx)
    dy = np.minimum(yy, h - 1 - yy)
    d = np.minimum(dx, dy)
    ramp = np.clip(d / feather_px, 0.0, 1.0)
    # Cosine-smoothed ramp: (1 - cos(pi*t)) / 2 — eases both ends
    ramp = (1 - np.cos(np.pi * ramp)) / 2.0
    a = (a * ramp).astype(np.uint8)
    rgb = np.array(patch.convert("RGB"))
    rgba = np.dstack([rgb, a])
    return Image.fromarray(rgba, mode="RGBA")


def verify_tileable(patch: Image.Image, out_path: Path) -> Path:
    """Write a 3×3 wrapped grid of the patch for manual seam inspection."""
    w, h = patch.size
    grid = Image.new("RGBA", (w * 3, h * 3), (0, 0, 0, 0))
    for gy in range(3):
        for gx in range(3):
            grid.paste(patch, (gx * w, gy * h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out_path, format="PNG")
    return out_path


def strip_alpha_for_tile(patch: Image.Image) -> Image.Image:
    """Drop the alpha channel — the engine tile layer is RGB, not RGBA."""
    return patch.convert("RGB")


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
