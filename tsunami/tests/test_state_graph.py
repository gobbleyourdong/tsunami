"""Unit tests for tsunami.animation.state_graph — schema + validator."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tsunami.animation.state_graph import (
    AnimationPrimitive,
    EntityGraph,
    StateDef,
    StateGraphValidationError,
    Transition,
    load_entity_graph,
    load_primitive,
    validate_entity_graph,
)


# ── Primitive tests ─────────────────────────────────────────────────

def test_primitive_shape_valid():
    p = AnimationPrimitive.model_validate({
        "primitive": "igniting",
        "category": "vfx",
        "frame_count": 3,
        "nudges": [
            {"delta": "small flames start at base"},
            {"delta": "flames climb up trunk"},
            {"delta": "full engulfment"},
        ],
    })
    assert p.primitive == "igniting"
    assert p.reversible is False  # default
    assert all(n.strength == 0.4 for n in p.nudges)  # default


def test_primitive_frame_count_must_match_nudges():
    with pytest.raises(ValueError, match="frame_count=5.*len.nudges.=3"):
        AnimationPrimitive.model_validate({
            "primitive": "mismatched",
            "category": "vfx",
            "frame_count": 5,
            "nudges": [
                {"delta": "a"},
                {"delta": "b"},
                {"delta": "c"},
            ],
        })


def test_primitive_extra_fields_forbidden():
    """Catches typos early — 'categry' instead of 'category' would
    silently pass with extra='allow'."""
    with pytest.raises(Exception):
        AnimationPrimitive.model_validate({
            "primitive": "p",
            "category": "vfx",
            "frame_count": 1,
            "categry": "typo-here",  # deliberate typo
            "nudges": [{"delta": "x"}],
        })


def test_load_primitive_from_yaml(tmp_path: Path):
    p_yaml = tmp_path / "wind_sway.yaml"
    p_yaml.write_text(yaml.safe_dump({
        "primitive": "wind_sway_loop",
        "category": "environment",
        "frame_count": 2,
        "reversible": True,
        "nudges": [
            {"delta": "branches lean slightly left", "strength": 0.2},
            {"delta": "branches return to center", "strength": 0.2},
        ],
    }))
    p = load_primitive(p_yaml)
    assert p.reversible is True
    assert p.nudges[0].strength == 0.2


# ── Entity-graph minimal construction ───────────────────────────────

def _minimal_graph_dict() -> dict:
    """One root state, one derived, one transition with an animation ref."""
    return {
        "entity": "test_entity",
        "base": "test/base.png",
        "states": {
            "idle": {"source": "base"},
            "active": {"derive_from": "idle", "prompt": "turned on, lit up"},
        },
        "transitions": [
            {"from": "idle", "to": "active", "on": "ACTIVATE",
             "animation": "activating"},
        ],
        "loops": {},
    }


def test_minimal_entity_graph_valid():
    g = EntityGraph.model_validate(_minimal_graph_dict())
    validate_entity_graph(g)  # no raise
    assert g.root_state() == "idle"
    assert g.transitions[0].identifier() == "idle→active"


def test_graph_rejects_two_roots():
    d = _minimal_graph_dict()
    d["states"]["active"] = {"source": "base"}  # second root
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError, match="exactly one root"):
        validate_entity_graph(g)


def test_graph_rejects_zero_roots():
    d = _minimal_graph_dict()
    d["states"]["idle"] = {"derive_from": "active", "prompt": "x"}  # no more root
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError, match="exactly one root"):
        validate_entity_graph(g)


def test_graph_rejects_unknown_derive_from():
    d = _minimal_graph_dict()
    d["states"]["active"] = {"derive_from": "ghost", "prompt": "x"}
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError, match="derive_from='ghost'"):
        validate_entity_graph(g)


def test_graph_rejects_derive_without_prompt():
    d = _minimal_graph_dict()
    d["states"]["active"] = {"derive_from": "idle"}  # no prompt
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError, match="no prompt"):
        validate_entity_graph(g)


def test_graph_rejects_derivation_cycle():
    d = _minimal_graph_dict()
    # idle → active → idle loop
    d["states"]["idle"] = {"derive_from": "active", "prompt": "from active"}
    d["states"]["active"] = {"derive_from": "idle", "prompt": "from idle"}
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError):
        validate_entity_graph(g)


def test_graph_rejects_unknown_transition_from():
    d = _minimal_graph_dict()
    d["transitions"].append(
        {"from": "ghost", "to": "idle", "on": "GOES",
         "animation": "whatever"}
    )
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError, match="from='ghost'"):
        validate_entity_graph(g)


def test_graph_rejects_unknown_transition_to():
    d = _minimal_graph_dict()
    d["transitions"].append(
        {"from": "idle", "to": "ghost", "on": "GOES",
         "animation": "whatever"}
    )
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError, match="to='ghost'"):
        validate_entity_graph(g)


def test_graph_transition_needs_animation_or_reverse_of():
    d = _minimal_graph_dict()
    d["transitions"] = [{"from": "idle", "to": "active", "on": "GOES"}]
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError,
                        match="animation or reverse_of"):
        validate_entity_graph(g)


def test_graph_reverse_of_must_resolve():
    d = _minimal_graph_dict()
    d["transitions"].append(
        {"from": "active", "to": "idle", "on": "DEACTIVATE",
         "reverse_of": "ghost→path"}
    )
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError, match="reverse_of"):
        validate_entity_graph(g)


def test_graph_reverse_of_resolves_cleanly():
    d = _minimal_graph_dict()
    d["transitions"].append(
        {"from": "active", "to": "idle", "on": "DEACTIVATE",
         "reverse_of": "idle→active"}  # exists
    )
    g = EntityGraph.model_validate(d)
    validate_entity_graph(g)  # no raise


def test_graph_loop_state_must_exist():
    d = _minimal_graph_dict()
    d["loops"] = {"ghost_loop": {"state": "ghost", "animation": "x"}}
    g = EntityGraph.model_validate(d)
    with pytest.raises(StateGraphValidationError, match="state='ghost'"):
        validate_entity_graph(g)


# ── Animation-dir file-existence check ──────────────────────────────

def test_graph_validates_animation_dir_references(tmp_path: Path):
    # Write a fake anim dir with one file present, one missing
    anim_dir = tmp_path / "animations"
    anim_dir.mkdir()
    (anim_dir / "activating.yaml").write_text("primitive: x\ncategory: vfx\n"
                                               "frame_count: 1\n"
                                               "nudges: [{delta: y}]\n")

    d = _minimal_graph_dict()
    g = EntityGraph.model_validate(d)

    # With a present ref — passes
    validate_entity_graph(g, animations_dir=anim_dir)

    # Add a transition pointing at a missing animation
    g.transitions.append(Transition(
        **{"from": "active", "to": "idle", "on": "DEACTIVATE"},
        animation="missing_primitive",
    ))
    with pytest.raises(StateGraphValidationError,
                        match="missing_primitive"):
        validate_entity_graph(g, animations_dir=anim_dir)


def test_load_entity_graph_from_yaml(tmp_path: Path):
    p = tmp_path / "entity.yaml"
    p.write_text(yaml.safe_dump(_minimal_graph_dict()))
    g = load_entity_graph(p)
    assert g.entity == "test_entity"
    assert len(g.transitions) == 1


def test_load_entity_graph_enforces_strict_mode(tmp_path: Path):
    """When animations_dir is passed, a missing ref is a load-time failure."""
    p = tmp_path / "entity.yaml"
    p.write_text(yaml.safe_dump(_minimal_graph_dict()))
    anim_dir = tmp_path / "animations"
    anim_dir.mkdir()  # empty — 'activating' ref won't resolve
    with pytest.raises(StateGraphValidationError, match="activating"):
        load_entity_graph(p, animations_dir=anim_dir)
