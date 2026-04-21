"""Postprocess for iso_character — alpha-crop + shared sprite_sheet_asm
for the movement-loop blockout assembly."""
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
    ISO_DIRECTIONS_8,
    assemble_movement_blockout,
)


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    a = np.array(img.split()[-1])
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop_frame(src: Path, out_dir: Path, pad_px: int = 24, out_side: int = 256) -> Path:
    """Tight alpha-bbox crop → pad to square → LANCZOS resize."""
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
    resized = canvas.resize((out_side, out_side), Image.LANCZOS)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / src.name
    resized.save(dst, format="PNG", optimize=True)
    return dst


def assemble_movement_loop_blockout(
    direction_to_frame: dict[str, Path],
    out_dir: Path,
    character_id: str = "character",
) -> dict[str, Path]:
    """Assemble the 8-direction movement-loop blockout sheet + manifest.

    Returns a dict of artifact paths: sheet, manifest, spec, labeled_preview.
    """
    spec = BlockoutSpec(
        directions=ISO_DIRECTIONS_8,
        anim_frame_targets={"idle": 4, "walk": 8, "run": 8, "attack": 6, "hurt": 3, "death": 6, "cast": 5},
        rotation_angles=8,
        projection="iso_dimetric_2to1",
        per_frame_ms_default=90,
    )
    sheet_path = out_dir / f"{character_id}_movement_blockout.png"
    manifest_path = out_dir / f"{character_id}_movement_blockout.manifest.json"
    labeled_path = out_dir / f"{character_id}_movement_blockout_preview.png"
    s, m, sp = assemble_movement_blockout(
        direction_to_frame, spec,
        out_sheet=sheet_path,
        out_manifest=manifest_path,
        labeled_preview=labeled_path,
    )
    return {"sheet": s, "manifest": m, "spec": sp, "labeled": labeled_path}


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
