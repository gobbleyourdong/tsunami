"""Postprocess for top_down_character workflow.

ERNIE-Image-Turbo with mode='icon' returns an RGBA PNG sized `canvas` (default
1024x1024) where every pose-cell has a transparent background (magenta
chromakeyed out upstream). This module:

  1. slice_grid(sheet_rgba, grid_w, grid_h)    → list[RGBA frames]
  2. normalize_palette(frames, max_colors)     → quantized frames, optional
  3. stitch_master(anim_name, dir_to_sheet)    → one tall RGBA PNG per anim with
                                                 directions stacked as rows
  4. assemble_movement_loop_blockout(paths, …) → 4-direction blockout sheet
                                                 + manifest using shared
                                                 _common/character_blockout

Slicing is deliberately dumb — identity held by seed discipline at gen time,
not by this module. The `assemble_movement_loop_blockout` entrypoint uses the
shared `_common/` helpers so the blockout artifact matches the format that
`iso_character` and (future) `side_scroller_character` and `character_animation`
workflows consume.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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


def _tight_crop(src: Path, out_side: int = 256, pad_px: int = 24) -> Image.Image:
    """Alpha-bbox tight crop → pad to square → LANCZOS resize.

    Returns the processed frame as a PIL Image (not saved). Used to
    normalize frames before they hit `assemble_movement_blockout`.
    """
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


def assemble_from_corpus(
    essence: str, animation_name: str,
    direction_to_frame: dict[str, Path],
    out_dir: Path, cell_px: int = 256,
) -> dict[str, Path] | None:
    """Assemble a blockout driven by a harvested corpus spec.

    Loads `scaffolds/.claude/blockouts/<essence>/<animation_name>.json`
    (emitted by `.claude/tools/character_blockout_extractor.py`) and
    uses its directions + anim_frame_targets instead of the hardcoded
    defaults in `assemble_movement_loop_blockout`. Identity in the
    output sheet's `.spec.json` carries back to the canonical source
    game — future animation passes can reference it for identity lock.

    Returns None if no corpus spec exists for (essence, animation_name).
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent / "_common"))
    from blockout_loader import load_blockout, to_blockout_spec  # noqa: E402
    from character_blockout import assemble_movement_blockout  # noqa: E402

    raw = load_blockout(essence, animation_name)
    if raw is None:
        return None
    spec = to_blockout_spec(raw)

    staging = out_dir / "_staging_blockout"
    staging.mkdir(parents=True, exist_ok=True)
    cropped_map: dict[str, Path] = {}
    for d, src in direction_to_frame.items():
        if not src.exists():
            continue
        cropped = _tight_crop(src, out_side=cell_px)
        p = staging / f"{essence}_{animation_name}_{d}.png"
        cropped.save(p, format="PNG", optimize=True)
        cropped_map[d] = p

    character_id = f"{essence}_{animation_name}"
    sheet_p, manifest_p, spec_p = assemble_movement_blockout(
        cropped_map, spec,
        out_sheet=out_dir / f"{character_id}_movement_blockout.png",
        out_manifest=out_dir / f"{character_id}_movement_blockout.manifest.json",
        labeled_preview=out_dir / f"{character_id}_movement_blockout_preview.png",
    )
    return {
        "sheet": sheet_p, "manifest": manifest_p, "spec": spec_p,
        "labeled": out_dir / f"{character_id}_movement_blockout_preview.png",
        "source_essence": essence,
        "source_animation": animation_name,
    }


def assemble_movement_loop_blockout(
    direction_to_frame: dict[str, Path],
    out_dir: Path,
    character_id: str = "character",
    cell_px: int = 256,
) -> dict[str, Path]:
    """Assemble a 4-direction (N/E/S/W) movement-loop blockout.

    Uses the shared `_common/character_blockout.py` helper so the output
    format matches `iso_character` and the (future) `character_animation`
    workflow's expected input.

    Each input frame is tight-cropped + LANCZOS-resized to `cell_px` square
    before assembly. Missing directions are skipped (manifest reflects only
    the present frames).
    """
    # Normalize frames: tight-crop each and save into a staging dir
    staging = out_dir / "_staging_blockout"
    staging.mkdir(parents=True, exist_ok=True)
    cropped_map: dict[str, Path] = {}
    for d, src in direction_to_frame.items():
        if not src.exists():
            continue
        cropped = _tight_crop(src, out_side=cell_px)
        p = staging / f"{character_id}_{d}.png"
        cropped.save(p, format="PNG", optimize=True)
        cropped_map[d] = p

    spec = BlockoutSpec(
        directions=ISO_DIRECTIONS_4,
        anim_frame_targets={"idle": 4, "walk": 8, "run": 8, "attack_light": 5, "attack_heavy": 7, "hurt": 3, "death": 6, "interact": 3},
        rotation_angles=4,
        projection="orthographic_top_down",
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
