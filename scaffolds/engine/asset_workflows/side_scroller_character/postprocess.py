"""Postprocess for side_scroller_character workflow.

Side-scroller characters are generated one pose per ERNIE call (see
`prompt_template.md` — the top_down_character canary round proved that
grid-prompting does not produce animation phases). This module:

  1. stack_horizontal(frames, out_path)  → one N-wide strip per anim
  2. flip_for_right_facing(frame)         → horizontal mirror for R-facing
  3. normalize_palette(frames, max_colors) → optional palette quantization
  4. to_thumbnail(src, dst, max_px)       → canary-size PNG thumbnailer

No grid slicing — each ERNIE output is already one 1024×1024 pose. The
pipeline crops to the character's bounding box (with a small pad) before
stacking, to minimize strip width without clipping motion blur / shadow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class CropSpec:
    pad_px: int = 12
    out_size: int = 256  # final per-frame size after alpha-bbox crop + resize


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Tight bounding box around all non-transparent pixels, else None."""
    a = np.array(img.split()[-1])
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop_and_resize(src: Path, spec: CropSpec, out_dir: Path) -> Path:
    """Crop to alpha bbox + pad, then fit-into-square at spec.out_size."""
    img = Image.open(src).convert("RGBA")
    bbox = alpha_bbox(img)
    if bbox is None:
        raise ValueError(f"empty alpha on {src}")
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - spec.pad_px)
    y0 = max(0, y0 - spec.pad_px)
    x1 = min(img.size[0], x1 + spec.pad_px)
    y1 = min(img.size[1], y1 + spec.pad_px)
    cropped = img.crop((x0, y0, x1, y1))
    # Fit into square by padding the short axis
    w, h = cropped.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - w) // 2, (side - h) // 2))
    resized = canvas.resize((spec.out_size, spec.out_size), Image.NEAREST)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / src.name
    resized.save(dst, format="PNG")
    return dst


def stack_horizontal(frames: Sequence[Path], out_path: Path) -> Path:
    """Concatenate equal-sized frames into a horizontal strip, one row."""
    imgs = [Image.open(p).convert("RGBA") for p in frames]
    w = sum(i.size[0] for i in imgs)
    h = max(i.size[1] for i in imgs)
    strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = 0
    for im in imgs:
        strip.paste(im, (x, 0))
        x += im.size[0]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_path, format="PNG")
    return out_path


def flip_for_right_facing(src: Path, dst: Path) -> Path:
    """Horizontal mirror for right-facing counterpart."""
    img = Image.open(src).convert("RGBA")
    flipped = ImageOps.mirror(img)
    dst.parent.mkdir(parents=True, exist_ok=True)
    flipped.save(dst, format="PNG")
    return dst


def normalize_palette(frames: Iterable[Path], max_colors: int = 32) -> None:
    """In-place palette quantization to `max_colors` colors, preserving alpha."""
    for p in frames:
        img = Image.open(p).convert("RGBA")
        rgb = img.convert("RGB").quantize(colors=max_colors, method=Image.Quantize.FASTOCTREE).convert("RGB")
        a = np.array(img.split()[-1])
        rgba = np.dstack([np.array(rgb), a])
        Image.fromarray(rgba, mode="RGBA").save(p, format="PNG")


def to_thumbnail(src: Path, dst: Path, max_px: int = 256, max_bytes: int = 48_000) -> Path:
    """Downscale + PNG-optimize to fit canary thumbnail budget."""
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
