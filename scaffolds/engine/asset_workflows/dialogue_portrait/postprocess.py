"""Postprocess for dialogue_portrait. Per-emotion static portraits — thin
pipeline: alpha-crop + optional frame border + thumbnail.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    a = np.array(img.split()[-1])
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop_portrait(src: Path, out_dir: Path, pad_px: int = 20, out_side: int = 256) -> Path:
    """Tight alpha-bbox crop, pad-to-square, resize to out_side.

    Portraits naturally come back with 15–25% empty magenta around the head;
    this tightens the framing so the UI picks up the head+shoulders only.
    """
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
    resized = canvas.resize((out_side, out_side), Image.LANCZOS)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / src.name
    resized.save(dst, format="PNG")
    return dst


def to_thumbnail(src: Path, dst: Path, max_px: int = 256, max_bytes: int = 48_000) -> Path:
    img = Image.open(src).convert("RGBA")
    side = max_px
    while True:
        w, h = img.size
        scale = min(side / max(w, h), 1.0)
        tw, th = max(1, int(w * scale)), max(1, int(h * scale))
        thumb = img.resize((tw, th), Image.LANCZOS) if scale < 1 else img
        dst.parent.mkdir(parents=True, exist_ok=True)
        thumb.save(dst, format="PNG", optimize=True)
        if dst.stat().st_size <= max_bytes or side <= 32:
            return dst
        side //= 2
