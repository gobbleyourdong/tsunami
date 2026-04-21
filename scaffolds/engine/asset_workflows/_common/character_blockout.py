"""character_blockout — movement-loop blockout primitives.

The Shoal pipeline ships character workflows in two phases:

1. **Blockout phase (this module)**: one canonical pose per (direction, anim).
   Enough to prove the character's identity + silhouette works in the
   engine. Scaffolds can lay out combat timing, collision, z-sorting, and
   camera framing against the blockout before full animation is generated.

2. **Full animation phase** (future — separate `character_animation` workflow):
   N frames per (direction, anim) interpolating the pose. Uses edit_image
   on the blockout baseline to preserve identity across frames.

A "movement loop blockout" = a single canonical pose per direction of
a movement cycle (walk, run), rendered one frame each. Hooks for the
future animation workflow:

- `BlockoutSpec.anim_frame_targets`: intended final frame count per anim
  (populated as metadata; this module doesn't use it).
- `BlockoutSpec.rotation_angles`: intended rotation step count for
  future rotation workflow (e.g. 8, 16, 32 direction support).

This module is deliberately thin — no ERNIE calls. Callers (character
workflows) call ERNIE themselves and pass the resulting frame paths to
`assemble_movement_blockout`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# Make sibling module importable when this runs outside the package
sys.path.insert(0, str(Path(__file__).parent))
from sprite_sheet_asm import (  # noqa: E402
    assemble_grid,
    assemble_labeled_grid,
    write_manifest,
)


# The 8 isometric compass directions (2:1 dimetric convention, clockwise from north)
ISO_DIRECTIONS_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
ISO_DIRECTIONS_4 = ["N", "E", "S", "W"]  # top_down simple
SIDE_DIRECTIONS_1 = ["left"]  # side-scroller — flip for right


@dataclass
class BlockoutSpec:
    """Shape of a movement-loop blockout for a character workflow.

    `directions` defines compass coverage. `anim_frame_targets` is a hint
    to the (future) animation workflow — e.g. {"walk": 8, "run": 8} means
    "when animation workflow later fills this in, expect 8 frames per
    direction per anim."
    """
    directions: Sequence[str]
    anim_frame_targets: dict[str, int] = field(default_factory=dict)
    rotation_angles: int = 8  # default; 16/32 for future higher-res rotation
    projection: str = "iso_dimetric_2to1"
    per_frame_ms_default: int = 100


def movement_loop_pose_descriptions(spec: BlockoutSpec) -> dict[str, str]:
    """Canonical mid-stride reference pose per direction — one frame each.

    The blockout uses a MID-STRIDE pose (knees bent, one foot forward) as
    the canonical single-frame representation of "this character moves".
    When the animation workflow later runs, it treats this pose as the
    'middle frame' of the walk cycle and interpolates outward.
    """
    directions_desc = {
        "N":  "facing away from camera toward the back of the scene",
        "NE": "facing up-and-right toward the upper-right corner",
        "E":  "facing right in full profile",
        "SE": "facing down-and-right toward the lower-right corner",
        "S":  "facing the camera toward the viewer",
        "SW": "facing down-and-left toward the lower-left corner",
        "W":  "facing left in full profile",
        "NW": "facing up-and-left toward the upper-left corner",
        "left": "facing left in full profile",
        "right": "facing right in full profile",
    }
    mid_stride = (
        "mid-stride walking pose, one leg forward and bent at the knee, "
        "one leg back with heel slightly lifted, torso slightly leaning "
        "forward, arms swinging counter to the legs — this is the "
        "canonical movement reference pose"
    )
    return {d: f"{directions_desc.get(d, d)}, {mid_stride}" for d in spec.directions}


def assemble_movement_blockout(
    frame_paths: dict[str, Path],
    spec: BlockoutSpec,
    out_sheet: Path,
    out_manifest: Path,
    labeled_preview: Path | None = None,
):
    """Build the blockout sheet + manifest from per-direction frames.

    `frame_paths` maps direction → path to the single generated frame.
    Frames are laid out in `spec.directions` order, one per cell.

    If `labeled_preview` is provided, also write a dev-view grid with
    direction labels under each cell.
    """
    ordered_paths = [frame_paths[d] for d in spec.directions if d in frame_paths]
    ordered_labels = [d for d in spec.directions if d in frame_paths]
    if len(ordered_paths) != len(spec.directions):
        missing = set(spec.directions) - set(frame_paths)
        print(f"[blockout] WARN missing directions: {sorted(missing)}")

    cols = min(4, len(ordered_paths))  # 4-wide is readable; 8 in 1 row is squished
    sheet, manifest = assemble_grid(ordered_paths, cols=cols, labels=ordered_labels)
    out_sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_sheet, format="PNG", optimize=True)
    write_manifest(manifest, out_manifest)
    if labeled_preview is not None:
        preview, _ = assemble_labeled_grid(ordered_paths, cols=cols, labels=ordered_labels)
        labeled_preview.parent.mkdir(parents=True, exist_ok=True)
        preview.save(labeled_preview, format="PNG", optimize=True)

    # Attach spec metadata (frame targets + rotation angles) to manifest companion
    meta = {
        "directions": list(spec.directions),
        "projection": spec.projection,
        "anim_frame_targets": spec.anim_frame_targets,
        "rotation_angles": spec.rotation_angles,
        "per_frame_ms_default": spec.per_frame_ms_default,
        "blockout_note": (
            "Each cell is a single canonical mid-stride pose per direction. "
            "Future character_animation workflow will interpolate outward from "
            "this reference frame to produce full N-frame cycles."
        ),
    }
    import json as _json
    spec_path = out_manifest.with_suffix(".spec.json")
    spec_path.write_text(_json.dumps(meta, indent=2))
    return out_sheet, out_manifest, spec_path
