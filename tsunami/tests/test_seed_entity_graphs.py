"""Integration test — the commit-4 seed entity graphs load + validate
against the commit-3 seed animation library in strict mode.

"Strict mode" = pass animations_dir to the validator so every animation
+ overlay reference is checked against an actual YAML file on disk.
This is the v10 Production-Firing Audit discipline applied to asset
graphs: a dangling ref is a build-time failure, not a silent skip at
runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsunami.animation.state_graph import (
    EntityGraph,
    StateGraphValidationError,
    load_entity_graph,
)


_REPO = Path(__file__).resolve().parent.parent.parent
_ENTITIES_DIR = _REPO / "scaffolds" / "engine" / "asset_library" / "entities"
_ANIMATIONS_DIR = _REPO / "scaffolds" / "engine" / "asset_library" / "animations"


def _all_entity_yamls() -> list[Path]:
    if not _ENTITIES_DIR.is_dir():
        return []
    return sorted(_ENTITIES_DIR.glob("*.yaml"))


def test_entities_dir_exists():
    assert _ENTITIES_DIR.is_dir(), (
        f"expected entity library at {_ENTITIES_DIR}"
    )


def test_seed_entities_present():
    """Commit 4 ships these 2 entity graphs."""
    expected = {"tree", "crystal_formation"}
    present = {p.stem for p in _all_entity_yamls()}
    missing = expected - present
    assert not missing, f"seed entities missing: {missing}"


@pytest.mark.parametrize("path", _all_entity_yamls(), ids=lambda p: p.stem)
def test_entity_graph_loads_and_validates_strict(path: Path):
    """Every entity YAML loads AND validates AND every animation/overlay
    reference resolves to a real file in the animations dir."""
    g = load_entity_graph(path, animations_dir=_ANIMATIONS_DIR)
    assert isinstance(g, EntityGraph)
    assert g.entity == path.stem, (
        f"{path.name}: entity name {g.entity!r} must match filename stem "
        f"{path.stem!r} (loader-lookup contract, mirrors primitive rule)"
    )


@pytest.mark.parametrize("path", _all_entity_yamls(), ids=lambda p: p.stem)
def test_entity_graph_has_root_state(path: Path):
    """Every entity exposes exactly one source=base root state."""
    g = load_entity_graph(path, animations_dir=_ANIMATIONS_DIR)
    assert g.root_state()  # raises if 0 or 2+


# ── Tree-specific checks ────────────────────────────────────────────

def test_tree_has_fire_lifecycle():
    """Tree's fire lifecycle wires the 3 commit-3 primitives — if any
    got mis-renamed, this catches it at load time."""
    g = load_entity_graph(_ENTITIES_DIR / "tree.yaml",
                          animations_dir=_ANIMATIONS_DIR)
    animations_used = {t.animation for t in g.transitions if t.animation}
    assert "igniting" in animations_used
    assert "water_extinguish" in animations_used
    assert "fire_fizzling" in animations_used


def test_tree_loops_exist_in_declared_states():
    """Every loop references a state that exists — validator enforces
    this, but we also verify the specific mappings."""
    g = load_entity_graph(_ENTITIES_DIR / "tree.yaml",
                          animations_dir=_ANIMATIONS_DIR)
    by_state = {lref.state: lref.animation for lref in g.loops.values()}
    assert by_state.get("windy") == "wind_sway_loop"
    assert by_state.get("on_fire") == "fire_flicker_loop"


# ── Crystal-specific: the reverse_of demo ───────────────────────────

def test_crystal_uses_reverse_of():
    """The crystal_formation graph demonstrates reverse_of: one
    primitive (shattering) powers two transitions via forward/reverse."""
    g = load_entity_graph(_ENTITIES_DIR / "crystal_formation.yaml",
                          animations_dir=_ANIMATIONS_DIR)
    forwards = [t for t in g.transitions if t.animation]
    reverses = [t for t in g.transitions if t.reverse_of]
    # Exactly one forward + one reverse
    assert len(forwards) == 1
    assert len(reverses) == 1
    # The reverse points at the forward's identifier
    assert reverses[0].reverse_of == forwards[0].identifier()
    # Both transitions route via the shattering primitive — one direct,
    # one by reference
    assert forwards[0].animation == "shattering"
