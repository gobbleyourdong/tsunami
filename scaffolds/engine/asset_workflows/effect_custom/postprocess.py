"""Postprocess for effect_custom workflow.

ERNIE returns 1024² RGBA (icon mode — magenta chromakey cleared).
Effects occupy a center region and usually come as a horizontal strip.
Pipeline:

  1. alpha_bbox_crop(img) — tight crop to non-transparent region
  2. split_strip(img, frame_count) — N equal cells
  3. align_frames(frames) — center-of-mass re-center per cell
  4. assemble_strip(cells, cell_px) — repack as canonical 1×N strip
  5. verify_loop_seam(frames) — pixel-diff first vs last frame for
     aura/atmospheric (loop-required sub_kinds)
  6. darken_to_transparent(img) — convert white backdrop to transparent
     for screen-blend auras (optional)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    arr = np.array(img.convert("RGBA"))
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def split_strip(img: Image.Image, frame_count: int) -> list[Image.Image]:
    """Cut a 1×N horizontal strip into N equal cells."""
    w, h = img.size
    cw = w // frame_count
    return [img.crop((i * cw, 0, (i + 1) * cw, h)) for i in range(frame_count)]


def center_pad_to_cell(img: Image.Image, cell_px: tuple[int, int]) -> Image.Image:
    """Resize-preserving-aspect + center-pad to cell_px with transparent."""
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


def align_frames(frames: list[Image.Image]) -> list[Image.Image]:
    """Re-center each frame around its alpha center-of-mass."""
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


def assemble_strip(
    src_path: Path, out_path: Path,
    cell_px: tuple[int, int], frame_count: int,
    do_align: bool = True,
) -> Path:
    """Multi-frame effect strip → canonical cell_px × frame_count output."""
    src = Image.open(src_path).convert("RGBA")
    cells = split_strip(src, frame_count)
    cleaned = []
    for c in cells:
        bbox = alpha_bbox(c)
        if bbox is None:
            cleaned.append(Image.new("RGBA", cell_px, (0, 0, 0, 0)))
            continue
        x0, y0, x1, y1 = bbox
        x0 = max(0, x0 - 1); y0 = max(0, y0 - 1)
        x1 = min(c.width, x1 + 1); y1 = min(c.height, y1 + 1)
        cropped = c.crop((x0, y0, x1, y1))
        cleaned.append(center_pad_to_cell(cropped, cell_px))
    finalized = align_frames(cleaned) if do_align else cleaned
    cw, ch = cell_px
    strip = Image.new("RGBA", (cw * frame_count, ch), (0, 0, 0, 0))
    for i, f in enumerate(finalized):
        strip.paste(f, (i * cw, 0), f)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_path)
    return out_path


def verify_loop_seam(strip_path: Path, frame_count: int, cell_px: tuple[int, int]) -> dict:
    """Compute pixel-diff between first and last frame of a loop-required
    effect (aura, atmospheric). Returns {rms_diff, pass_threshold} —
    scaffolds decide what's acceptable."""
    src = Image.open(strip_path).convert("RGBA")
    cells = split_strip(src, frame_count)
    if len(cells) < 2:
        return {"rms_diff": 0.0, "pass_threshold": 30.0, "ok": True, "note": "single-frame; no seam"}
    first = np.array(cells[0]).astype(np.float32)
    last = np.array(cells[-1]).astype(np.float32)
    if first.shape != last.shape:
        return {"rms_diff": -1.0, "pass_threshold": 30.0, "ok": False, "note": "frame size mismatch"}
    diff = first - last
    rms = float(np.sqrt((diff * diff).mean()))
    threshold = 30.0  # RMS units — empirical
    return {
        "rms_diff": rms,
        "pass_threshold": threshold,
        "ok": rms < threshold,
        "note": f"loop seam rms={rms:.1f} vs threshold={threshold:.0f}",
    }


def darken_to_transparent(
    src_path: Path, out_path: Path,
    darkness_threshold: int = 20,
) -> Path:
    """For aura_vfx with screen-blend: convert near-white-backdrop pixels
    to transparent. Darkness_threshold is the per-channel distance from
    white below which pixels get alpha=0 (treating the backdrop as
    "close to white")."""
    img = Image.open(src_path).convert("RGBA")
    arr = np.array(img)
    # Distance from white [255, 255, 255] in RGB
    rgb = arr[:, :, :3].astype(np.int32)
    dist_from_white = np.abs(rgb - 255).max(axis=2)
    mask_near_white = dist_from_white < darkness_threshold
    arr[mask_near_white, 3] = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, mode="RGBA").save(out_path)
    return out_path
