"""Postprocess for side_scroller_character workflow.

Side-scroller characters are generated one pose per ERNIE call (see
`prompt_template.md` — the top_down_character canary round proved that
grid-prompting does not produce animation phases). This module:

  1. stack_horizontal(frames, out_path)            → one N-wide strip per anim
  2. flip_for_right_facing(frame)                   → horizontal mirror for R-facing
  3. normalize_palette(frames, max_colors)          → optional palette quantization
  4. to_thumbnail(src, dst, max_px)                 → canary-size PNG thumbnailer
  5. assemble_movement_loop_blockout(paths, …)      → 1-direction (left) blockout
                                                     using shared _common helpers

No grid slicing — each ERNIE output is already one 1024×1024 pose. The
pipeline crops to the character's bounding box (with a small pad) before
stacking, to minimize strip width without clipping motion blur / shadow.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

# _common is a sibling dir of this workflow
sys.path.insert(0, str(Path(__file__).parent.parent / "_common"))
from sprite_sheet_asm import assemble_grid, write_manifest  # noqa: E402
from character_blockout import (  # noqa: E402
    BlockoutSpec,
    SIDE_DIRECTIONS_1,
    assemble_movement_blockout,
)
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


def _tight_crop(src: Path, out_side: int = 256, pad_px: int = 24) -> Image.Image:
    """Alpha-bbox tight crop → pad to square → LANCZOS resize."""
    img = Image.open(src).convert("RGBA")
    a = np.array(img.split()[-1])
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        raise ValueError(f"empty alpha on {src}")
    x0, y0 = int(xs.min()), int(ys.min())
    x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
    x0 = max(0, x0 - pad_px); y0 = max(0, y0 - pad_px)
    x1 = min(img.size[0], x1 + pad_px); y1 = min(img.size[1], y1 + pad_px)
    cropped = img.crop((x0, y0, x1, y1))
    w, h = cropped.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - w) // 2, (side - h) // 2))
    return canvas.resize((out_side, out_side), Image.LANCZOS)


def assemble_movement_loop_blockout(
    left_frame: Path,
    out_dir: Path,
    character_id: str = "character",
    cell_px: int = 256,
) -> dict[str, Path]:
    """Assemble a 1-direction (left baseline) movement-loop blockout.

    Side-scroller characters have a single baseline direction (left);
    the right-facing variant is a horizontal flip at render time. This
    blockout ships the single mid-stride canonical pose using the shared
    `_common/character_blockout.py` helper so the output format matches
    `iso_character`'s 8-direction and `top_down_character`'s 4-direction
    blockouts — the future `character_animation` workflow consumes all
    three uniformly.
    """
    staging = out_dir / "_staging_blockout"
    staging.mkdir(parents=True, exist_ok=True)
    cropped = _tight_crop(left_frame, out_side=cell_px)
    p = staging / f"{character_id}_left.png"
    cropped.save(p, format="PNG", optimize=True)
    cropped_map = {"left": p}

    spec = BlockoutSpec(
        directions=SIDE_DIRECTIONS_1,
        anim_frame_targets={
            "idle": 6, "walk": 8, "run": 8, "jump_up": 3, "jump_peak": 1,
            "jump_down": 2, "land": 2, "attack_light": 5, "attack_heavy": 8,
            "hurt": 3, "death": 6, "wall_slide": 2, "dash": 4, "crouch": 2,
            "crouch_walk": 6,
        },
        rotation_angles=1,  # side_scroller is one-direction + flip
        projection="side_profile_2d",
        per_frame_ms_default=90,
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
