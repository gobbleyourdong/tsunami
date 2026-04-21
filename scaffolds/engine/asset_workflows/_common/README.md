# _common/

Shared helpers for Shoal asset workflows. Anything useful across more
than one workflow lands here instead of being copy-pasted per workflow.

## Modules

### `sprite_sheet_asm.py`

The canonical sprite-sheet assembler. Takes N frame PNGs and produces:

- `assemble_strip(frames)` — horizontal N×1 strip
- `assemble_grid(frames, cols)` — grid layout, rows auto-computed
- `assemble_labeled_grid(frames, cols, labels)` — dev-view grid with
  per-cell label strips (for README thumbnails and human review, NOT
  engine-consumed)
- `write_manifest(manifest, path)` / `read_manifest(path)` — JSON
  (de)serialization of the cell coordinates + labels

Manifest format:

```json
{
  "cols": 4, "rows": 2,
  "cell_w": 256, "cell_h": 256,
  "gutter_px": 0,
  "sheet_w": 1024, "sheet_h": 512,
  "frame_count": 8,
  "cells": [
    {"index": 0, "label": "N", "cell_x": 0, "cell_y": 0, "cell_w": 256, "cell_h": 256, "source": "iso_N.png"},
    ...
  ]
}
```

Engines read this to look up "which cell holds frame X" without
inspecting the image. Primary source of truth.

### `character_blockout.py`

Movement-loop blockout primitives for character workflows. Ships two
phases of a character's animation pipeline:

1. **Blockout (now)** — one canonical pose per direction per movement
   anim. Enough to prove identity and silhouette; scaffolds can lay out
   combat timing, collision bounds, z-sorting against it.
2. **Full animation (future)** — N frames per (direction, anim) produced
   by a later `character_animation` workflow that uses `edit_image` on
   the blockout baseline to preserve identity across interpolated
   frames.

Constants:
- `ISO_DIRECTIONS_8` — standard 8 compass directions for iso characters
- `ISO_DIRECTIONS_4` — 4 cardinals for top_down
- `SIDE_DIRECTIONS_1` — single left baseline (flip for right) for
  side_scroller

Helpers:
- `movement_loop_pose_descriptions(spec)` → `{direction: pose_desc}`
  for each direction, ready to drop into an ERNIE prompt template.
- `assemble_movement_blockout(frame_paths, spec, out_sheet, out_manifest,
  labeled_preview)` → writes the sheet, JSON manifest, and a
  `.spec.json` companion with forward-looking metadata (frame targets,
  rotation angles) for the future animation workflow to read.

## Usage from a workflow

```python
import sys
from pathlib import Path

# Workflow is at scaffolds/engine/asset_workflows/<name>/; _common is a sibling
sys.path.insert(0, str(Path(__file__).parent.parent / "_common"))
from character_blockout import (
    BlockoutSpec, ISO_DIRECTIONS_8, movement_loop_pose_descriptions,
    assemble_movement_blockout,
)
from sprite_sheet_asm import assemble_grid, write_manifest
```

## Future additions (deliberate stubs)

- `character_animation.py` (future workflow) — interpolates the blockout
  pose into N frames per anim per direction using `edit_image` on the
  reference frame.
- `character_rotation.py` (future workflow) — produces per-angle rotated
  sprites at the configured `rotation_angles` (8/16/32/64) — for fake
  3D sprite rotation in top-down and iso scaffolds.
- `palette_ops.py` (when a scaffold needs strict retro palettes) —
  consolidate the `normalize_palette(max_colors=N)` discipline
  currently duplicated across per-workflow postprocess modules.
