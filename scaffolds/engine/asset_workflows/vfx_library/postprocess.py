"""Postprocess for vfx_library workflow.

Each VFX frame comes back from `/v1/workflows/icon` as a single-pose RGBA
PNG with magenta chromakeyed out. Pipeline:

  1. alpha_bbox_crop(frame)              → tight crop + pad
  2. stack_horizontal(frames, out_path)  → one N-wide spritesheet per VFX
  3. center_frame_in_square(frame, side) → fixed-size square for grid-consumers
  4. to_thumbnail(src, dst, max_px)      → canary thumbnail

VFX have no character-identity constraint across frames, so there's no
`seed-pinning-per-character` concern here. Pin seeds per (vfx_name,
frame_index) from `anim_set.json::vfx[*].seed_base + frame_index` for
reproducibility across library rebuilds.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    a = np.array(img.split()[-1])
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def alpha_bbox_crop(src: Path, out_dir: Path, pad_px: int = 24, out_side: int = 256) -> Path:
    """Tight alpha-bbox crop, then pad to square, then resize to out_side."""
    img = Image.open(src).convert("RGBA")
    bbox = alpha_bbox(img)
    if bbox is None:
        raise ValueError(f"empty alpha on {src}")
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad_px)
    y0 = max(0, y0 - pad_px)
    x1 = min(img.size[0], x1 + pad_px)
    y1 = min(img.size[1], y1 + pad_px)
    cropped = img.crop((x0, y0, x1, y1))
    w, h = cropped.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - w) // 2, (side - h) // 2))
    resized = canvas.resize((out_side, out_side), Image.NEAREST)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / src.name
    resized.save(dst, format="PNG")
    return dst


def stack_horizontal(frames: Sequence[Path], out_path: Path) -> Path:
    """Concatenate equal-sized frames into a horizontal spritesheet."""
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


def center_frame_in_square(src: Path, dst: Path, out_side: int = 128) -> Path:
    """Paste an arbitrary-size frame centered inside an out_side² square,
    preserving alpha. For grid-aligned engines that need fixed tile dims."""
    img = Image.open(src).convert("RGBA")
    canvas = Image.new("RGBA", (out_side, out_side), (0, 0, 0, 0))
    w, h = img.size
    if max(w, h) > out_side:
        scale = out_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.NEAREST)
        w, h = img.size
    canvas.paste(img, ((out_side - w) // 2, (out_side - h) // 2))
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst, format="PNG")
    return dst


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
