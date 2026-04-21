"""Postprocess for ui_hud: alpha-bbox crop + optional 9-slice decomposition.

Three operations covering the 3 kinds:
  1. crop_to_ui_element(src, out_wh)  — panels/buttons/bars tight-crop + LANCZOS resize
  2. slice_9slice(src, out_dir, corner_px) — decompose a panel into 9 tiles
  3. to_thumbnail(src, dst) — canary thumbnail
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


def crop_to_ui_element(src: Path, out_dir: Path, out_w: int, out_h: int, pad_px: int = 12) -> Path:
    """Tight alpha-bbox crop and LANCZOS resize to (out_w, out_h).

    Does NOT preserve aspect ratio — UI elements have a target size the
    engine expects; we let the subject stretch to fit. If aspect
    mismatch is severe (> 1.5x), re-run the gen at an aspect closer to
    the target.
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
    resized = cropped.resize((out_w, out_h), Image.LANCZOS)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / src.name
    resized.save(dst, format="PNG", optimize=True)
    return dst


def slice_9slice(src: Path, out_dir: Path, corner_px: int = 64) -> dict[str, Path]:
    """Decompose a panel source into 9 regions (tl/t/tr/l/c/r/bl/b/br).

    Each region is saved as its own PNG. The engine assembles them at
    render time:
      - corners (tl/tr/bl/br) never stretch.
      - edges (t/b) stretch horizontally only.
      - edges (l/r) stretch vertically only.
      - center (c) stretches both axes.
    """
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    c = corner_px
    if w < 2 * c + 1 or h < 2 * c + 1:
        raise ValueError(f"panel too small ({w}x{h}) for corner_px={c}")
    out_dir.mkdir(parents=True, exist_ok=True)
    regions = {
        "tl": (0, 0, c, c),
        "t":  (c, 0, w - c, c),
        "tr": (w - c, 0, w, c),
        "l":  (0, c, c, h - c),
        "c":  (c, c, w - c, h - c),
        "r":  (w - c, c, w, h - c),
        "bl": (0, h - c, c, h),
        "b":  (c, h - c, w - c, h),
        "br": (w - c, h - c, w, h),
    }
    out_paths: dict[str, Path] = {}
    for tag, box in regions.items():
        piece = img.crop(box)
        p = out_dir / f"{src.stem}__{tag}.png"
        piece.save(p, format="PNG", optimize=True)
        out_paths[tag] = p
    return out_paths


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
