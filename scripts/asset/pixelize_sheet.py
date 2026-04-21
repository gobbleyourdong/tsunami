"""Pixelize a full-res sprite sheet → target grid size.

Terminal pass of the asset-graph pipeline: takes a bake output directory
(states/, transitions/, loops/, sheet.png, metadata.json — all at
generation resolution, typically 1024²) and emits a pixelized companion:

  sheet_<N>.png         — cells at N×N pixels
  metadata_<N>.json     — same rows/cells structure, frame_size updated

Never feeds back into rotations or further edits — canonical full-res
frames stay in place so a different target grid (or a different
quantization strategy) can always be re-baked from the same source.

Downsample strategy: whole-sheet LANCZOS. The sheet has no inter-cell
margins, so per-cell LANCZOS vs whole-sheet LANCZOS is equivalent and
the one-shot form is faster. For classic "nearest-neighbor retro" look,
pass --filter nearest; for smooth modern pixelart look, the default
lanczos preserves more detail at low target sizes.

Usage:
  python scripts/asset/pixelize_sheet.py --bake /tmp/bake_crystal_v2 --size 128
  python scripts/asset/pixelize_sheet.py --bake /tmp/bake_crystal_v2 --size 64 --filter nearest
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from PIL import Image

log = logging.getLogger("pixelize")


_FILTERS = {
    "lanczos": Image.LANCZOS,
    "bicubic": Image.BICUBIC,
    "bilinear": Image.BILINEAR,
    "nearest": Image.NEAREST,
}


def _compose_rgba_sheet_from_unmix(bake_dir: Path, meta: dict) -> Image.Image:
    """If extract_alpha_unmix has produced _rgba.png siblings, rebuild the
    sheet from THOSE instead of the magenta-bg sheet.png. Returns a fresh
    RGBA PIL image at the same layout the bake composed.

    Returns None if the _rgba.png set is incomplete (any expected frame
    missing) — caller then falls back to sheet.png.
    """
    src_fw = meta["frame_size"]["w"]
    src_fh = meta["frame_size"]["h"]
    rows = len(meta["rows"])
    cols = max((r["frame_count"] for r in meta["rows"]), default=0)

    out = Image.new("RGBA", (cols * src_fw, rows * src_fh), (0, 0, 0, 0))
    any_used = False
    for r in meta["rows"]:
        for c in r["cells"]:
            # Row's source frames live under transitions/<name>/ or
            # loops/<name>/; derive from the row's `name` field plus the
            # col_index. Bake stores frame_NNN.png → _rgba.png siblings.
            # We don't know the exact dir from metadata alone, so search.
            frame_idx = c["col_index"]
            candidates = list(bake_dir.rglob(f"frame_{frame_idx:03d}_rgba.png"))
            # Filter by row name match (transition id or loop name appears
            # in the parent dir)
            match = None
            for p in candidates:
                if r["name"].replace("→", "__") in str(p):
                    match = p
                    break
            if match is None:
                return None  # incomplete — fall back
            cell = Image.open(match).convert("RGBA")
            # Resize if sizes don't match (shouldn't normally)
            if cell.size != (src_fw, src_fh):
                cell = cell.resize((src_fw, src_fh), Image.LANCZOS)
            out.paste(cell, (c["col_index"] * src_fw, r["row_index"] * src_fh))
            any_used = True
    return out if any_used else None


def pixelize_sheet(bake_dir: Path, target_size: int,
                   filter_name: str = "lanczos") -> tuple[Path, Path]:
    """Read bake_dir's sheet.png + metadata.json, produce pixelized copies.

    If `extract_alpha_unmix.py` has already produced `_rgba.png` siblings
    for every frame, compose a fresh RGBA sheet from those — bypasses the
    magenta background in sheet.png. Otherwise fall back to sheet.png
    (which still has the magenta canvas visible).

    Returns (new_sheet_path, new_metadata_path)."""
    sheet_path = bake_dir / "sheet.png"
    meta_path = bake_dir / "metadata.json"
    if not sheet_path.is_file():
        raise FileNotFoundError(f"missing sheet at {sheet_path}")
    if not meta_path.is_file():
        raise FileNotFoundError(f"missing metadata at {meta_path}")
    if filter_name not in _FILTERS:
        raise ValueError(f"unknown filter {filter_name!r}; pick one of {list(_FILTERS)}")

    meta = json.loads(meta_path.read_text())
    src_fw = meta["frame_size"]["w"]
    src_fh = meta["frame_size"]["h"]
    rows = len(meta["rows"])
    cols = max((r["frame_count"] for r in meta["rows"]), default=0)

    rgba_composed = _compose_rgba_sheet_from_unmix(bake_dir, meta)
    if rgba_composed is not None:
        sheet = rgba_composed
        log.info(f"[pixelize] using _rgba.png siblings (alpha-extracted)")
    else:
        sheet = Image.open(sheet_path).convert("RGBA")
        log.info(f"[pixelize] using sheet.png (magenta-bg — run extract_alpha_unmix first for clean RGBA)")
    expected_w, expected_h = cols * src_fw, rows * src_fh
    if sheet.size != (expected_w, expected_h):
        log.warning(
            f"[pixelize] sheet size {sheet.size} != metadata-expected "
            f"({expected_w}, {expected_h}); resizing treats the sheet as-is"
        )

    # Whole-sheet one-shot downsample. cols*target, rows*target keeps each
    # cell at exactly target_size so downstream cell indexing stays clean.
    #
    # Critical: premultiply RGB by α before resize. Without this, LANCZOS
    # (and bicubic/bilinear) mix RGB values from low-α "background" pixels
    # into their high-α neighbors during downsample — producing colored
    # fringes around the subject at low target sizes. Unpremultiplying
    # after resize restores straight alpha. NEAREST is unaffected (no
    # inter-pixel mixing), but the branch runs uniformly for simplicity.
    new_w, new_h = cols * target_size, rows * target_size
    filt = _FILTERS[filter_name]
    import numpy as np
    arr = np.asarray(sheet).astype(np.float32)  # H×W×4, 0-255
    alpha = arr[..., 3:4] / 255.0
    premult = arr.copy()
    premult[..., :3] = premult[..., :3] * alpha
    premult_im = Image.fromarray(premult.astype(np.uint8), mode="RGBA")
    pm_small = premult_im.resize((new_w, new_h), filt)
    pm_small_arr = np.asarray(pm_small).astype(np.float32)
    small_alpha = pm_small_arr[..., 3:4] / 255.0
    # Avoid divide-by-zero; where α is ~0, color doesn't matter so leave 0.
    safe_a = np.clip(small_alpha, 1e-6, 1.0)
    straight = pm_small_arr.copy()
    straight[..., :3] = np.clip(pm_small_arr[..., :3] / safe_a, 0, 255)
    pixelized = Image.fromarray(straight.astype(np.uint8), mode="RGBA")

    out_sheet = bake_dir / f"sheet_{target_size}.png"
    pixelized.save(out_sheet)
    log.info(
        f"[pixelize] {sheet.size} → {pixelized.size} "
        f"(filter={filter_name}, {cols}×{rows} cells at {target_size}px) "
        f"→ {out_sheet}"
    )

    # Build derivative metadata. Preserve all row-level info (kind,
    # primitive, total_strength, deltas) and rewrite per-cell geometry.
    new_rows = []
    for r in meta["rows"]:
        new_cells = [
            {**c,
             "x": c["col_index"] * target_size,
             "y": r["row_index"] * target_size,
             "w": target_size, "h": target_size}
            for c in r["cells"]
        ]
        new_rows.append({**r, "cells": new_cells})

    new_meta = {
        **meta,
        "frame_size": {"w": target_size, "h": target_size},
        "pixelization": f"pixelized {src_fw}→{target_size} via {filter_name}",
        "source_sheet": sheet_path.name,
        "rows": new_rows,
    }
    out_meta = bake_dir / f"metadata_{target_size}.json"
    out_meta.write_text(json.dumps(new_meta, indent=2))
    log.info(f"[pixelize] metadata → {out_meta}")
    return out_sheet, out_meta


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--bake", required=True, type=Path,
                   help="bake output directory (must contain sheet.png + metadata.json)")
    p.add_argument("--size", type=int, required=True,
                   help="target cell size in pixels (e.g. 64, 128, 256)")
    p.add_argument("--filter", default="lanczos",
                   choices=sorted(_FILTERS.keys()),
                   help="downsample filter (default lanczos for smooth; "
                        "use nearest for harsh retro pixel-art look)")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    if not args.bake.is_dir():
        print(f"ERROR: bake dir not found: {args.bake}", file=sys.stderr)
        return 2
    if args.size < 8 or args.size > 1024:
        print(f"ERROR: --size {args.size} outside sane range [8, 1024]",
              file=sys.stderr)
        return 2
    pixelize_sheet(args.bake, args.size, args.filter)
    return 0


if __name__ == "__main__":
    sys.exit(main())
