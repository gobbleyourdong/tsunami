"""Bridge: `scaffolds/.claude/blockouts/<essence>/<anim>.json` →
`BlockoutSpec` objects the legacy character workflows consume.

The harvester `.claude/tools/character_blockout_extractor.py` converts
sister's direction-tagged character extractions into JSON specs. This
module loads those specs + adapts them into the `BlockoutSpec`
dataclass + per-direction prompt dicts that iso_character /
top_down_character / top_down_jrpg_character / side_scroller_character
workflows already know how to drive.

Sister's actual progression_description goes into the base prompt, so
the identity-description comes from canonical games — not from
hand-authored template slots in each workflow.

Usage (from inside a character workflow):

    from blockout_loader import (
        load_blockout, list_blockouts, blockout_prompts,
    )

    # List everything available for a given projection
    specs = list_blockouts(projection="top_down")  # or "iso", "side_scroller"
    # → [{essence, animation_name, directions, rotation_angles, ...}, ...]

    # Load one by (essence, animation_name) and get per-direction prompts
    spec = load_blockout("1986_dragon_quest", "hero_plainclothes_walk")
    per_dir_prompts = blockout_prompts(spec)
    # → {'N': 'Pixel-art character sprite — hero plainclothes walk... facing away', 'E': ..., ...}

The workflow then fires ERNIE per direction using the pre-composed
prompts + the spec's shared seed_label.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# Resolve CLAUDE_ROOT by walking up from this module's path.
# _common/blockout_loader.py → asset_workflows/_common → engine →
# scaffolds → ark. `.claude/blockouts/` is a sibling of engine/.
_THIS = Path(__file__).resolve()
_CLAUDE_ROOT = _THIS.parent.parent.parent.parent / ".claude"
BLOCKOUTS_DIR = _CLAUDE_ROOT / "blockouts"

# Sibling module for adapting → BlockoutSpec
sys.path.insert(0, str(Path(__file__).parent))
from character_blockout import (  # noqa: E402
    BlockoutSpec,
    movement_loop_pose_descriptions,
)


def _infer_projection(rotation_angles: int) -> str:
    """4-dir → top_down, 8-dir → iso, 1-dir → side_scroller."""
    if rotation_angles >= 8:
        return "iso"
    if rotation_angles >= 4:
        return "top_down"
    return "side_scroller"


def load_blockout(essence: str, animation_name: str) -> Optional[dict]:
    """Load one harvested spec. Returns the raw dict (not a BlockoutSpec
    — see `to_blockout_spec` for adaptation)."""
    safe = animation_name.replace("/", "_")
    path = BLOCKOUTS_DIR / essence / f"{safe}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def to_blockout_spec(raw: dict) -> BlockoutSpec:
    """Adapt the harvester's raw JSON into a BlockoutSpec dataclass."""
    directions = raw.get("directions") or []
    rotation_angles = raw.get("rotation_angles") or (8 if len(directions) >= 8 else 4)
    anim_frame_targets = raw.get("anim_frame_targets") or {}
    projection_label = _infer_projection(rotation_angles)
    # BlockoutSpec uses "iso_dimetric_2to1" for iso, others per convention
    projection = {
        "iso":          "iso_dimetric_2to1",
        "top_down":     "top_down_orthographic",
        "side_scroller": "side_profile",
    }.get(projection_label, "iso_dimetric_2to1")
    return BlockoutSpec(
        directions=directions,
        anim_frame_targets=anim_frame_targets,
        rotation_angles=rotation_angles,
        projection=projection,
    )


def list_blockouts(projection: Optional[str] = None) -> list[dict]:
    """List all harvested blockout specs. Optional `projection` filter:
    'iso' | 'top_down' | 'side_scroller'."""
    if not BLOCKOUTS_DIR.is_dir():
        return []
    out = []
    for essence_dir in sorted(BLOCKOUTS_DIR.iterdir()):
        if not essence_dir.is_dir():
            continue
        for f in sorted(essence_dir.glob("*.json")):
            try:
                raw = json.loads(f.read_text())
            except Exception:
                continue
            rot = raw.get("rotation_angles") or 4
            infer_proj = _infer_projection(rot)
            if projection and infer_proj != projection:
                continue
            raw["_projection"] = infer_proj
            raw["_path"] = str(f)
            out.append(raw)
    return out


def blockout_prompts(raw: dict) -> dict[str, str]:
    """Compose per-direction ERNIE prompts from a harvested spec.

    Reuses the base_prompt_template (which carries the identity from
    sister's progression_description) + appends the direction-specific
    pose clause from `movement_loop_pose_descriptions`."""
    spec = to_blockout_spec(raw)
    pose_by_dir = movement_loop_pose_descriptions(spec)
    template = raw.get("base_prompt_template") or ""
    out: dict[str, str] = {}
    for direction in spec.directions:
        pose_clause = pose_by_dir.get(direction, direction)
        # Append the direction-specific pose description to the identity-
        # anchored template. The template already ends with the
        # "N-direction blockout" note, so we add the per-direction detail.
        out[direction] = f"{template} Specifically: {pose_clause}."
    return out


def blockout_seed(raw: dict) -> str:
    """Deterministic seed-label for ERNIE (pin across all N directions
    of one character to preserve identity)."""
    return raw.get("seed_label") or f"{raw.get('essence', 'unknown')}_{raw.get('animation_name', 'unknown')}"


# Convenience: inventory by essence
def list_by_essence(essence: str) -> list[dict]:
    if not BLOCKOUTS_DIR.is_dir():
        return []
    ed = BLOCKOUTS_DIR / essence
    if not ed.is_dir():
        return []
    out = []
    for f in sorted(ed.glob("*.json")):
        try:
            raw = json.loads(f.read_text())
            raw["_path"] = str(f)
            out.append(raw)
        except Exception:
            continue
    return out
