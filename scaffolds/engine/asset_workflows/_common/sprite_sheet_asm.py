"""sprite_sheet_asm — shared sprite-sheet assembler for Shoal workflows.

Any workflow that produces N frames (character animations, VFX sequences,
UI-state variants, iso directions) can assemble them into a single grid
sprite sheet through this module. Returns the sheet PNG plus a manifest
JSON so engines can look up "which cell holds frame X" without opening
the image.

Design goals:
- **One function per shape**: single strip (N×1), grid (cols×rows), padded
  grid (with configurable gutter), labeled grid (dev-view with tags).
- **No assumptions about frame size**: inspects first input, applies a
  uniform cell size = max(w) × max(h), pads smaller frames centered.
- **Manifest is the source of truth**: the engine reads it to find
  (cell_x, cell_y, cell_w, cell_h, label) for each frame. Sheet image is
  just bytes; manifest is meaning.
- **Alpha preserved throughout**: RGBA in, RGBA out.

Usage:
  from _common.sprite_sheet_asm import assemble_grid, write_manifest
  sheet, manifest = assemble_grid(
      frames=[Path("f_00.png"), Path("f_01.png"), ...],
      cols=4,
      labels=["walk_0", "walk_1", "walk_2", "walk_3"],
  )
  sheet.save("walk_sheet.png")
  write_manifest(manifest, "walk_sheet.manifest.json")
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image


@dataclass
class CellManifest:
    index: int
    label: str | None
    cell_x: int
    cell_y: int
    cell_w: int
    cell_h: int
    source: str | None  # original frame path, if known


@dataclass
class SheetManifest:
    cols: int
    rows: int
    cell_w: int
    cell_h: int
    gutter_px: int
    sheet_w: int
    sheet_h: int
    frame_count: int
    cells: list[CellManifest]


def _uniform_cell_size(frames: Sequence[Image.Image]) -> tuple[int, int]:
    w = max(f.size[0] for f in frames)
    h = max(f.size[1] for f in frames)
    return w, h


def assemble_strip(
    frames: Sequence[Path | Image.Image],
    labels: Sequence[str] | None = None,
    gutter_px: int = 0,
) -> tuple[Image.Image, SheetManifest]:
    """Horizontal N×1 strip."""
    return assemble_grid(frames, cols=len(frames), labels=labels, gutter_px=gutter_px)


def assemble_grid(
    frames: Sequence[Path | Image.Image],
    cols: int,
    rows: int | None = None,
    labels: Sequence[str] | None = None,
    gutter_px: int = 0,
) -> tuple[Image.Image, SheetManifest]:
    """Grid layout. rows auto-computes as ceil(len/cols)."""
    imgs = [Image.open(f).convert("RGBA") if isinstance(f, Path) else f.convert("RGBA") for f in frames]
    sources = [str(f) if isinstance(f, Path) else None for f in frames]
    if not imgs:
        raise ValueError("assemble_grid: no frames provided")
    n = len(imgs)
    rows = rows or ((n + cols - 1) // cols)
    cell_w, cell_h = _uniform_cell_size(imgs)
    sheet_w = cols * cell_w + (cols - 1) * gutter_px
    sheet_h = rows * cell_h + (rows - 1) * gutter_px
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    cells: list[CellManifest] = []
    for i, im in enumerate(imgs):
        col = i % cols
        row = i // cols
        x = col * (cell_w + gutter_px)
        y = row * (cell_h + gutter_px)
        # Center the frame inside its cell if it's smaller than the uniform size
        w, h = im.size
        dx = (cell_w - w) // 2
        dy = (cell_h - h) // 2
        sheet.paste(im, (x + dx, y + dy), im)
        label = labels[i] if labels and i < len(labels) else None
        cells.append(CellManifest(
            index=i, label=label, cell_x=x, cell_y=y,
            cell_w=cell_w, cell_h=cell_h,
            source=sources[i],
        ))
    manifest = SheetManifest(
        cols=cols, rows=rows, cell_w=cell_w, cell_h=cell_h,
        gutter_px=gutter_px, sheet_w=sheet_w, sheet_h=sheet_h,
        frame_count=n, cells=cells,
    )
    return sheet, manifest


def assemble_labeled_grid(
    frames: Sequence[Path | Image.Image],
    cols: int,
    labels: Sequence[str],
    label_height_px: int = 24,
    gutter_px: int = 8,
    bg_color: tuple[int, int, int, int] = (40, 40, 40, 255),
) -> tuple[Image.Image, SheetManifest]:
    """Dev-view grid with a dark background and label strips below each cell.

    Pure visualization helper — not what ships to the engine. Engines get
    the no-label grid + manifest; this is for README thumbnails and
    human review.
    """
    if len(labels) != len(frames):
        raise ValueError(f"labels ({len(labels)}) must match frames ({len(frames)})")
    try:
        from PIL import ImageDraw, ImageFont
    except ImportError as e:
        raise ImportError("PIL ImageDraw/ImageFont required for labeled grid") from e

    imgs = [Image.open(f).convert("RGBA") if isinstance(f, Path) else f.convert("RGBA") for f in frames]
    n = len(imgs)
    rows = (n + cols - 1) // cols
    cell_w, cell_h = _uniform_cell_size(imgs)
    tile_h = cell_h + label_height_px
    sheet_w = cols * cell_w + (cols + 1) * gutter_px
    sheet_h = rows * tile_h + (rows + 1) * gutter_px
    sheet = Image.new("RGBA", (sheet_w, sheet_h), bg_color)
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    cells: list[CellManifest] = []
    for i, im in enumerate(imgs):
        col = i % cols
        row = i // cols
        x = gutter_px + col * (cell_w + gutter_px)
        y = gutter_px + row * (tile_h + gutter_px)
        dx = (cell_w - im.size[0]) // 2
        dy = (cell_h - im.size[1]) // 2
        sheet.paste(im, (x + dx, y + dy), im)
        label_y = y + cell_h + 4
        if font is not None:
            draw.text((x + 4, label_y), labels[i][:28], fill=(220, 220, 220, 255), font=font)
        cells.append(CellManifest(
            index=i, label=labels[i], cell_x=x, cell_y=y,
            cell_w=cell_w, cell_h=cell_h, source=None,
        ))
    manifest = SheetManifest(
        cols=cols, rows=rows, cell_w=cell_w, cell_h=cell_h,
        gutter_px=gutter_px, sheet_w=sheet_w, sheet_h=sheet_h,
        frame_count=n, cells=cells,
    )
    return sheet, manifest


def write_manifest(manifest: SheetManifest, out_path: Path) -> Path:
    """Serialize the manifest to JSON. One source of truth for engines."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(manifest)
    out_path.write_text(json.dumps(data, indent=2))
    return out_path


def read_manifest(path: Path) -> SheetManifest:
    data = json.loads(path.read_text())
    cells = [CellManifest(**c) for c in data.pop("cells")]
    return SheetManifest(**data, cells=cells)
