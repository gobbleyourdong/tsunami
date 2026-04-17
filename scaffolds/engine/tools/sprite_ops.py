"""Post-process op registry + chain runner.

An op is a named function that transforms a sprite image (or a list of
them, for splitter/collector ops) in the post-processing pipeline. The
registry is declarative so categories can reference ops by name in
their `post_process: list[str]` config.

v1.1 ships 17 ops — 7 ported from sprite_pipeline.py + 10 new per
recipes/note_001. Four more are deferred to v1.2 (autotile_variant_gen,
unify_palette, parallax_depth_tag, nine_slice_detect).

Op semantics:
  - Plain op:    Image → Image
  - Splitter:    Image → list[Image]  (is_splitter=True)
  - Collector:   list[Image] → Image  (is_collector=True)
  - Annotator:   list[Image] → list[Image], may attach per-item
                 metadata via context.per_item_metadata
  - Side-effect: op may write into context.metadata_updates (e.g.
                 additive_blend_tag emits `composite_mode: 'add'`)

Chain fan-out rule: exactly one splitter and one collector per chain.
A chain with two splitters or a splitter without a collector errors
with `chain_fan_out_invalid`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

from PIL import Image

# ─── OpSpec + registry ───────────────────────────────────────────────

@dataclass
class OpSpec:
    name: str
    is_splitter: bool = False
    is_collector: bool = False
    side_effects: list[str] = field(default_factory=list)


# v1.1 registry. Impls come from sprite_ops_impl; OPS is the metadata
# side, OP_IMPLS is the callable side. They match by name at
# registration (at module import below).

OPS: dict[str, OpSpec] = {
    # Ported from sprite_pipeline.py.
    "pixel_extract":           OpSpec("pixel_extract"),
    "isolate_largest":         OpSpec("isolate_largest"),
    "trim_transparent":        OpSpec("trim_transparent"),
    "center_crop_object":      OpSpec("center_crop_object"),
    "quantize_palette":        OpSpec("quantize_palette"),
    "pixel_snap":              OpSpec("pixel_snap"),
    "normalize_height":        OpSpec("normalize_height"),
    # New in v1.1 (recipes/note_001).
    "grid_cut":                OpSpec("grid_cut", is_splitter=True),
    "seamless_check":          OpSpec("seamless_check"),
    "pack_spritesheet":        OpSpec("pack_spritesheet", is_collector=True),
    "horizontal_tileable_fix": OpSpec("horizontal_tileable_fix"),
    "flat_color_quantize":     OpSpec("flat_color_quantize"),
    "radial_alpha_cleanup":    OpSpec("radial_alpha_cleanup"),
    "preserve_fragmentation":  OpSpec("preserve_fragmentation"),
    "additive_blend_tag":      OpSpec("additive_blend_tag",
                                      side_effects=["metadata:composite_mode"]),
    "eye_center":              OpSpec("eye_center"),
    "head_only_crop":          OpSpec("head_only_crop"),
}

# v1.2 deferred (documented here so the registry is a single source of
# truth — tests can check that these are NOT present until v1.2 lands):
V1_2_DEFERRED = {
    "autotile_variant_gen", "unify_palette",
    "parallax_depth_tag", "nine_slice_detect",
}

# Impl callables populated by sprite_ops_impl on import.
OpImpl = Callable[..., Any]
OP_IMPLS: dict[str, OpImpl] = {}


def register_op(name: str, fn: OpImpl) -> None:
    if name not in OPS:
        raise ValueError(
            f"register_op: {name!r} not in OPS registry. Declare the "
            f"OpSpec first or switch the name."
        )
    OP_IMPLS[name] = fn


# ─── Pipeline context ────────────────────────────────────────────────

@dataclass
class PipelineContext:
    """Carried through a chain run. Ops read from it (category-level
    hints like target_size, metadata the author passed) and may write
    into `metadata_updates` to surface post-gen data to generate_asset."""
    category: str
    asset_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    target_size: tuple[int, int] = (64, 64)
    palette_colors: int = 16
    # Ops populate this; generate_asset merges onto AssetRecord.metadata.
    metadata_updates: dict[str, Any] = field(default_factory=dict)
    # Atlas JSON from pack_spritesheet or other collectors.
    atlas: Optional[dict[str, Any]] = None


@dataclass
class ChainResult:
    output: Union[Image.Image, list[Image.Image]]
    metadata_updates: dict[str, Any]
    atlas: Optional[dict[str, Any]] = None


# ─── Chain validation ────────────────────────────────────────────────

class ChainFanOutInvalid(ValueError):
    """Raised when a post_process chain's splitter/collector shape is
    structurally invalid — surfaced to the validator as
    `chain_fan_out_invalid`."""


def validate_chain(chain: list[str]) -> None:
    """Structural check the chain before any image work starts. Catches
    bad chains at configure time rather than mid-build."""
    splitter_count = 0
    collector_count = 0
    seen_splitter_before_collector = False
    for name in chain:
        if name not in OPS:
            raise ValueError(f"unknown_op: {name!r} not in OPS registry")
        spec = OPS[name]
        if spec.is_splitter:
            if seen_splitter_before_collector:
                raise ChainFanOutInvalid(
                    f"chain has two splitters before a collector "
                    f"(second is {name!r})"
                )
            splitter_count += 1
            seen_splitter_before_collector = True
        if spec.is_collector:
            collector_count += 1
            seen_splitter_before_collector = False

    if splitter_count != collector_count:
        raise ChainFanOutInvalid(
            f"splitter/collector mismatch: {splitter_count} splitters, "
            f"{collector_count} collectors — chains must pair them 1:1"
        )


# ─── Chain runner ────────────────────────────────────────────────────

def run_chain(
    img: Image.Image,
    chain: list[str],
    context: PipelineContext,
) -> ChainResult:
    """Walk the post_process chain. Splitter ops open a fan-out — each
    subsequent op runs on each element of the list until a collector
    closes it. Missing impls raise cleanly (not a silent skip)."""
    validate_chain(chain)

    cur: Union[Image.Image, list[Image.Image]] = img
    for name in chain:
        spec = OPS[name]
        fn = OP_IMPLS.get(name)
        if fn is None:
            raise ValueError(
                f"op {name!r} has no registered impl "
                f"(did sprite_ops_impl import run?)"
            )
        if isinstance(cur, list):
            if spec.is_collector:
                cur = fn(cur, context)
            else:
                # Per-item fan. Annotator ops (list→list) still walk
                # this path — they just return each element as-is.
                cur = [fn(x, context) for x in cur]
        else:
            cur = fn(cur, context)

    return ChainResult(
        output=cur,
        metadata_updates=dict(context.metadata_updates),
        atlas=context.atlas,
    )


# Register the impls by importing the module — sprite_ops_impl side-
# effect-calls register_op for every op in OPS. Kept at bottom so the
# spec + registry above are the canonical API surface.
#
# The tools/ directory isn't a Python package (no __init__.py — its
# files are also invoked as scripts). We import by name via the same
# sys.path the tools scripts share.
import sprite_ops_impl  # noqa: F401,E402

# Sanity check at import: every OPS entry has an impl. Catches
# typos / missed registrations at module load instead of mid-pipeline.
_missing = sorted(set(OPS) - set(OP_IMPLS))
if _missing:
    raise RuntimeError(
        f"sprite_ops: ops without impls — {_missing}. "
        f"Fix sprite_ops_impl before using this registry."
    )
