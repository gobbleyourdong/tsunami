"""Validate every seed animation primitive YAML loads through the schema.

This is the integration point that would have caught the dead-fix-claim
pattern if we ever shipped a primitive that the schema couldn't parse —
before v10's Production-Firing Audit, a broken YAML might sit in the
library dead, referenced by entity graphs that silently skip it. The
schema validator + this test close that gap at the library-author step.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsunami.animation.state_graph import (
    AnimationPrimitive,
    load_primitive,
)


_REPO = Path(__file__).resolve().parent.parent.parent
_ANIMATIONS_DIR = _REPO / "scaffolds" / "engine" / "asset_library" / "animations"


def _all_yaml_files() -> list[Path]:
    if not _ANIMATIONS_DIR.is_dir():
        return []
    return sorted(_ANIMATIONS_DIR.glob("*.yaml"))


def test_animations_dir_exists():
    assert _ANIMATIONS_DIR.is_dir(), (
        f"expected animation library at {_ANIMATIONS_DIR}"
    )


def test_seed_primitives_present():
    """Commit 3 ships these 6 primitives; their YAML files must exist."""
    expected = {
        "wind_sway_loop",
        "fire_flicker_loop",
        "igniting",
        "fire_fizzling",
        "water_extinguish",
        "shattering",
    }
    present = {p.stem for p in _all_yaml_files()}
    missing = expected - present
    assert not missing, f"seed primitives missing: {missing}"


@pytest.mark.parametrize("path", _all_yaml_files(), ids=lambda p: p.stem)
def test_primitive_loads_and_validates(path: Path):
    """Every YAML in the library directory parses AND validates."""
    p = load_primitive(path)
    assert isinstance(p, AnimationPrimitive)
    # Primitive name matches filename stem — caught lazily otherwise
    assert p.primitive == path.stem, (
        f"{path.name}: primitive name {p.primitive!r} must match stem "
        f"{path.stem!r} (loader-lookup contract)"
    )


@pytest.mark.parametrize("path", _all_yaml_files(), ids=lambda p: p.stem)
def test_primitive_categories_are_known(path: Path):
    """Category vocabulary — keeps downstream tooling (bake tool,
    runtime loader) free of surprise strings."""
    p = load_primitive(path)
    assert p.category in {"character", "vfx", "environment", "prop"}, (
        f"{path.name}: unknown category {p.category!r}"
    )


@pytest.mark.parametrize("path", _all_yaml_files(), ids=lambda p: p.stem)
def test_primitive_strengths_bounded(path: Path):
    """Every nudge's strength stays in the chain-friendly range.
    This is the drift-bounding invariant from sigma draft_023: low
    per-step strengths + semantic deltas = bounded identity drift
    across the chain."""
    p = load_primitive(path)
    for i, n in enumerate(p.nudges):
        assert 0.15 <= n.strength <= 0.6, (
            f"{path.name} nudge {i}: strength={n.strength} "
            f"outside [0.15, 0.6]; identity drift is not bounded "
            f"with per-step strength that high/low"
        )


@pytest.mark.parametrize("path", _all_yaml_files(), ids=lambda p: p.stem)
def test_primitive_cumulative_strength_sane(path: Path):
    """Σstrength across the chain — proxy for cumulative drift bound.
    Hard ceiling ~3.0 because beyond that, identity is probably lost
    regardless of semantic cleverness."""
    p = load_primitive(path)
    total = sum(n.strength for n in p.nudges)
    assert total <= 3.0, (
        f"{path.name}: Σstrength={total:.2f} > 3.0; chain too aggressive"
    )
