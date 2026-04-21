"""Postprocess for top_down_character workflow.

ERNIE-Image-Turbo with mode='icon' returns an RGBA PNG sized `canvas` (default
1024x1024) where every pose-cell has a transparent background (magenta
chromakeyed out upstream). This module:

  1. slice_grid(sheet_rgba, grid_w, grid_h)  → list[RGBA frames]
  2. normalize_palette(frames, max_colors)   → quantized frames, optional
  3. stitch_master(anim_name, dir_to_sheet)  → one tall RGBA PNG per anim with
                                               directions stacked as rows

The pipeline is deliberately dumb — no anchor detection, no sub-pixel recentering.
Identity is held by the seed discipline at generation time; this module just
slices the grid ERNIE already laid out.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class SliceSpec:
    grid_w: int
    grid_h: int
    frame_out: int  # target per-frame size after downscale, e.g. 128 or 256


def slice_grid(sheet_path: Path, spec: SliceSpec, out_dir: Path) -> list[Path]:
    """Slice a sheet into grid_w * grid_h per-frame PNGs at spec.frame_out."""
    sheet = Image.open(sheet_path).convert("RGBA")
    w, h = sheet.size
    cell_w = w // spec.grid_w
    cell_h = h // spec.grid_h
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    idx = 0
    for row in range(spec.grid_h):
        for col in range(spec.grid_w):
            box = (col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
            frame = sheet.crop(box)
            if (cell_w, cell_h) != (spec.frame_out, spec.frame_out):
                frame = frame.resize((spec.frame_out, spec.frame_out), Image.NEAREST)
            p = out_dir / f"frame_{idx:02d}.png"
            frame.save(p, format="PNG")
            paths.append(p)
            idx += 1
    return paths


def normalize_palette(frames: Iterable[Path], max_colors: int = 32) -> None:
    """In-place palette quantization to `max_colors` colors, preserving alpha."""
    from PIL import Image as _I

    for p in frames:
        img = _I.open(p).convert("RGBA")
        # Separate alpha; quantize RGB only.
        rgb = img.convert("RGB").quantize(colors=max_colors, method=_I.Quantize.FASTOCTREE).convert("RGB")
        a = np.array(img.split()[-1])
        rgba = np.dstack([np.array(rgb), a])
        _I.fromarray(rgba, mode="RGBA").save(p, format="PNG")


def stitch_master(
    anim_name: str,
    per_direction_sheets: dict[str, Path],
    out_path: Path,
) -> Path:
    """Stack per-direction sheets vertically into one master per-anim sheet.

    Row order follows the `directions.order` array from anim_set.json:
    north, east, south, west. Missing directions are skipped (no blank rows
    reserved) — engines that consume this must honor the `directions` key in
    anim_set.json for row-index lookup.
    """
    order = ["north", "east", "south", "west"]
    rows = [per_direction_sheets[d] for d in order if d in per_direction_sheets]
    if not rows:
        raise ValueError(f"stitch_master[{anim_name}]: no direction sheets supplied")
    imgs = [Image.open(p).convert("RGBA") for p in rows]
    w = max(i.size[0] for i in imgs)
    h = sum(i.size[1] for i in imgs)
    master = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    for im in imgs:
        master.paste(im, (0, y))
        y += im.size[1]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    master.save(out_path, format="PNG")
    return out_path


def to_thumbnail(src: Path, dst: Path, max_px: int = 256, max_bytes: int = 48_000) -> Path:
    """Downscale + PNG-optimize to fit canary thumbnail budget.

    Target ≤ `max_bytes` (default 48 KB, leaves headroom below the 50 KB cap).
    Iteratively halves the longer side until under budget.
    """
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
