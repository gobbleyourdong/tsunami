"""Postprocess for projectile_sprites workflow.

ERNIE returns 1024² RGBA (mode='icon' → magenta chromakey removed).
Projectiles occupy a small central region. This module:

  1. alpha_bbox_crop(img) — tight crop to the non-transparent pixel region
  2. center_pad_to_cell(img, cell_px) — pad or downscale to target cell size
  3. split_4frame_strip(img, cell_px) — extract 4 cells from a wide strip
  4. align_frames(frames) — re-center each frame around its alpha center-of-mass
  5. assemble_single(src, cell_px) — crop + resize to single canonical cell
  6. assemble_strip(src, cell_px, frame_count) — crop + split + align + pack
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Return (x0, y0, x1, y1) of the non-transparent pixel region, or
    None if fully transparent."""
    arr = np.array(img.convert("RGBA"))
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def alpha_bbox_crop(src_path: Path, pad_px: int = 2) -> Image.Image:
    """Open + alpha-bbox crop + pad. Returns RGBA."""
    img = Image.open(src_path).convert("RGBA")
    bbox = alpha_bbox(img)
    if bbox is None:
        # Degenerate — return empty 16×16
        return Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad_px)
    y0 = max(0, y0 - pad_px)
    x1 = min(img.width, x1 + pad_px)
    y1 = min(img.height, y1 + pad_px)
    return img.crop((x0, y0, x1, y1))


def center_pad_to_cell(
    img: Image.Image, cell_px: tuple[int, int],
) -> Image.Image:
    """Resize (preserving aspect) to fit within cell_px, then center-pad
    with transparent pixels to reach cell_px exactly."""
    cw, ch = cell_px
    iw, ih = img.size
    scale = min(cw / iw, ch / ih)
    new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
    resized = img.resize(new_size, Image.LANCZOS)
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ox = (cw - new_size[0]) // 2
    oy = (ch - new_size[1]) // 2
    canvas.paste(resized, (ox, oy), resized)
    return canvas


def split_4frame_strip(
    img: Image.Image, frame_count: int,
) -> list[Image.Image]:
    """Cut a 1×N horizontal strip into N equal-width cells."""
    w, h = img.size
    cw = w // frame_count
    return [img.crop((i * cw, 0, (i + 1) * cw, h)) for i in range(frame_count)]


def align_frames(frames: list[Image.Image]) -> list[Image.Image]:
    """Re-center each frame around its alpha center-of-mass so the
    projectile doesn't appear to judder across cells. Returns new frames
    same-size as input but with content re-centered."""
    out = []
    for f in frames:
        arr = np.array(f)
        alpha = arr[:, :, 3]
        ys, xs = np.where(alpha > 0)
        if len(xs) == 0:
            out.append(f)
            continue
        cx, cy = int(xs.mean()), int(ys.mean())
        w, h = f.size
        shift_x = w // 2 - cx
        shift_y = h // 2 - cy
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(f, (shift_x, shift_y), f)
        out.append(canvas)
    return out


def assemble_single(
    src_path: Path, out_path: Path, cell_px: tuple[int, int] = (16, 16),
) -> Path:
    """Single-frame projectile: crop-to-alpha + pad to cell_px."""
    cropped = alpha_bbox_crop(src_path, pad_px=1)
    padded = center_pad_to_cell(cropped, cell_px)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    padded.save(out_path)
    return out_path


def assemble_strip(
    src_path: Path, out_path: Path,
    cell_px: tuple[int, int] = (16, 16), frame_count: int = 4,
) -> Path:
    """4-frame travel animation: ERNIE output is expected to be a
    horizontal strip composition. Split into N cells, alpha-align,
    re-pack as a canonical 1×N strip at cell_px resolution."""
    src = Image.open(src_path).convert("RGBA")
    cells = split_4frame_strip(src, frame_count)
    # Per-cell: crop to alpha bbox + pad to cell_px
    cleaned = []
    for c in cells:
        arr = np.array(c)
        bbox = alpha_bbox(c)
        if bbox is None:
            cleaned.append(Image.new("RGBA", cell_px, (0, 0, 0, 0)))
            continue
        x0, y0, x1, y1 = bbox
        x0 = max(0, x0 - 1); y0 = max(0, y0 - 1)
        x1 = min(c.width, x1 + 1); y1 = min(c.height, y1 + 1)
        cropped = c.crop((x0, y0, x1, y1))
        cleaned.append(center_pad_to_cell(cropped, cell_px))
    aligned = align_frames(cleaned)
    cw, ch = cell_px
    strip = Image.new("RGBA", (cw * frame_count, ch), (0, 0, 0, 0))
    for i, f in enumerate(aligned):
        strip.paste(f, (i * cw, 0), f)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_path)
    return out_path
