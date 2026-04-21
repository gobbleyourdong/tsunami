"""Postprocess for top_down_jrpg_character — 48×48 RPG-Maker pixel-art scale.

Unlike other character workflows, this one uses NEAREST downscaling to
preserve hard 1-pixel edges. LANCZOS smooths pixel art into mush at 48px.
Uses the shared _common/ helpers for blockout assembly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

# _common is a sibling dir of this workflow
sys.path.insert(0, str(Path(__file__).parent.parent / "_common"))
from sprite_sheet_asm import assemble_grid, write_manifest  # noqa: E402
from character_blockout import (  # noqa: E402
    BlockoutSpec,
    ISO_DIRECTIONS_4,
    assemble_movement_blockout,
)


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    a = np.array(img.split()[-1])
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop_to_pixel_sprite(src: Path, out_side: int = 48, pad_px: int = 16) -> Image.Image:
    """Alpha-bbox tight crop → pad to square → NEAREST downscale to out_side.

    NEAREST is intentional — preserves hard pixel edges. Do NOT use LANCZOS
    here.
    """
    img = Image.open(src).convert("RGBA")
    bbox = alpha_bbox(img)
    if bbox is None:
        raise ValueError(f"empty alpha on {src}")
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad_px); y0 = max(0, y0 - pad_px)
    x1 = min(img.size[0], x1 + pad_px); y1 = min(img.size[1], y1 + pad_px)
    cropped = img.crop((x0, y0, x1, y1))
    w, h = cropped.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - w) // 2, (side - h) // 2))
    # Staged downscale: first to ~2x target with LANCZOS to preserve feature
    # structure, then NEAREST to target to snap to pixel grid. This hybrid
    # gives cleaner pixel-art than direct NEAREST from 1024px (which loses
    # too much detail) or pure LANCZOS (which smears edges).
    intermediate = canvas.resize((out_side * 4, out_side * 4), Image.LANCZOS)
    final = intermediate.resize((out_side, out_side), Image.NEAREST)
    return final


def assemble_movement_loop_blockout(
    direction_to_frame: dict[str, Path],
    out_dir: Path,
    character_id: str = "character",
    cell_px: int = 48,
) -> dict[str, Path]:
    """4-direction JRPG-scale blockout. Uses shared _common helpers."""
    staging = out_dir / "_staging_blockout"
    staging.mkdir(parents=True, exist_ok=True)
    cropped_map: dict[str, Path] = {}
    for d, src in direction_to_frame.items():
        if not src.exists():
            continue
        cropped = crop_to_pixel_sprite(src, out_side=cell_px, pad_px=16)
        p = staging / f"{character_id}_{d}.png"
        cropped.save(p, format="PNG", optimize=True)
        cropped_map[d] = p

    spec = BlockoutSpec(
        directions=ISO_DIRECTIONS_4,
        anim_frame_targets={"walk": 3},  # JRPG 3-frame walk, middle=idle
        rotation_angles=4,
        projection="orthographic_top_down_small",
        per_frame_ms_default=180,  # JRPG walks are slow
    )
    sheet, manifest, sp = assemble_movement_blockout(
        cropped_map, spec,
        out_sheet=out_dir / f"{character_id}_movement_blockout.png",
        out_manifest=out_dir / f"{character_id}_movement_blockout.manifest.json",
        labeled_preview=out_dir / f"{character_id}_movement_blockout_preview.png",
    )
    return {
        "sheet": sheet,
        "manifest": manifest,
        "spec": sp,
        "labeled": out_dir / f"{character_id}_movement_blockout_preview.png",
    }


def to_thumbnail(src: Path, dst: Path, max_px: int = 256, max_bytes: int = 48_000) -> Path:
    """Thumbnail with NEAREST so pixel-art canaries stay crispy."""
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
