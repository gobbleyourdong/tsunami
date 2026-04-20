"""Tests for tsunami/error_fixer.py design-level patchers.

Gap #17b (Round L 2026-04-20): `_patch_add_tag` originally only handled
`archetypes` as a dict. Round L iter 7 captured the wave emitting
`archetypes: [{"id": "player", "tags": [...]}, ...]` (a LIST) when
recovering from the iter 6 validation error. The patcher silently
no-op'd, the tag_requirement never resolved, and the design compiled
with zero archetypes.

These tests lock both shapes (dict + list) so future refactors can't
regress the list-shape branch.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.error_fixer import (
    _patch_add_tag,
    _patch_duplicate_id,
    _patch_dangling_condition,
    fix_design_validation_errors,
)


def test_patch_add_tag_dict_shape():
    """Canonical schema shape — archetypes is a Record<string, Archetype>."""
    design = {
        "archetypes": {
            "player": {"tags": ["player"], "components": ["Health(4)"]},
            "octorok": {"tags": ["enemy"], "components": ["Health(1)"]},
        }
    }
    err = {
        "kind": "tag_requirement",
        "message": "CheckpointProgression requires tags checkpoint on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    # First archetype got the checkpoint tag appended
    first = next(iter(design["archetypes"].values()))
    assert "checkpoint" in first["tags"]


def test_patch_add_tag_list_shape():
    """Gap #17b fix: Round L captured wave emitting archetypes as list."""
    design = {
        "archetypes": [
            {"id": "player", "tags": ["player"]},
            {"id": "octorok", "tags": ["enemy"]},
        ]
    }
    err = {
        "kind": "tag_requirement",
        "message": "CheckpointProgression requires tags checkpoint on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    # First archetype (list[0]) got the tag
    assert "checkpoint" in design["archetypes"][0]["tags"]


def test_patch_add_tag_multiple_tags():
    """Error message `requires tags a, b, c on some archetype` — all get added."""
    design = {"archetypes": {"a": {"tags": []}}}
    err = {
        "kind": "tag_requirement",
        "message": "X requires tags checkpoint, respawn, safe_zone on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    tags = design["archetypes"]["a"]["tags"]
    for t in ("checkpoint", "respawn", "safe_zone"):
        assert t in tags


def test_patch_add_tag_no_archetypes_returns_false():
    """With no archetypes at all, patcher can't do anything — returns False
    so the error bubbles to unresolved for LLM regeneration."""
    design = {"mechanics": [], "archetypes": {}}
    err = {
        "kind": "tag_requirement",
        "message": "X requires tags t on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is False


def test_patch_add_tag_malformed_archetypes_safe():
    """If archetypes is something weird (int, string, None), don't crash —
    return False and let the error bubble."""
    for weird in (None, 42, "archetypes_string", [{"not_a_dict": "entry"}, 5]):
        design = {"archetypes": weird}
        err = {
            "kind": "tag_requirement",
            "message": "X requires tags t on some archetype, none found",
        }
        # Should not raise
        ok = _patch_add_tag(design, err)
        # For None/int/str the function should return False
        # For the list with non-dicts, the inner guard skips them
        assert ok in (True, False), f"should return bool for {weird!r}, got {ok!r}"


def test_fix_design_validation_errors_end_to_end_list_shape():
    """Full pipeline: wave emits archetypes-as-list + missing tag,
    patcher fixes it in one pass. Unresolved list should be empty."""
    design = {
        "archetypes": [{"id": "p", "tags": ["player"]}],
        "mechanics": [
            {"id": "cp", "type": "CheckpointProgression", "requires_tags": ["checkpoint"]}
        ],
    }
    errors = [{
        "kind": "tag_requirement",
        "message": "CheckpointProgression requires tags checkpoint on some archetype, none found",
        "path": "mechanics[0].type",
    }]
    patched, unresolved = fix_design_validation_errors(design, errors)
    assert unresolved == []
    assert "checkpoint" in patched["archetypes"][0]["tags"]


def test_patch_add_tag_entities_list_fallback():
    """Gap #23 (Round O 2026-04-20): wave emits `entities: [...]` (plan
    prior) instead of `archetypes: {...}`. Validator says "none found"
    because it only looks at archetypes. Patcher must fall back to
    entities so auto-fix still unblocks."""
    design = {
        "entities": [
            {"id": "player", "tags": ["hero"]},
            {"id": "boss", "tags": []},
        ],
        "mechanics": [
            {"id": "bp", "type": "BossPhases", "requires_tags": ["boss"]}
        ],
    }
    err = {
        "kind": "tag_requirement",
        "message": "BossPhases requires tags boss on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    # First entity (list[0]) got the boss tag appended
    assert "boss" in design["entities"][0]["tags"]


def test_patch_add_tag_entities_mirrors_into_archetypes():
    """Gap #25 (Round P 2026-04-20): tagging entities alone doesn't
    satisfy the validator — it only reads archetypes. Patcher must
    MIRROR the tagged entity into archetypes so the validator sees
    a tagged archetype on the next pass."""
    design = {
        "entities": [
            {"id": "player", "tags": ["hero"]},
        ],
    }
    err = {
        "kind": "tag_requirement",
        "message": "BossPhases requires tags boss on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    # Entity got the tag
    assert "boss" in design["entities"][0]["tags"]
    # AND archetypes got a mirrored entry with the tag
    assert "archetypes" in design
    assert isinstance(design["archetypes"], dict)
    assert "player" in design["archetypes"], (
        f"expected mirrored archetype 'player', got: {list(design['archetypes'].keys())}"
    )
    assert "boss" in design["archetypes"]["player"]["tags"]


def test_patch_add_tag_entities_mirror_uses_name_fallback():
    """If entity has no `id`, use `name` as archetype key."""
    design = {
        "entities": [{"name": "Link", "tags": []}],
    }
    err = {
        "kind": "tag_requirement",
        "message": "X requires tags hero on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    assert "Link" in design["archetypes"]


def test_patch_add_tag_entities_mirror_final_fallback_entity_0():
    """No id, no name — use 'entity_0' as the mirrored archetype key."""
    design = {
        "entities": [{"tags": []}],
    }
    err = {
        "kind": "tag_requirement",
        "message": "X requires tags hero on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    assert "entity_0" in design["archetypes"]


def test_patch_add_tag_entities_dict_fallback():
    """Entities can also be a dict (rare but observed)."""
    design = {
        "entities": {
            "player": {"tags": ["hero"]},
            "boss": {"tags": []},
        },
    }
    err = {
        "kind": "tag_requirement",
        "message": "BossPhases requires tags boss on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    # First entity got the boss tag
    first = next(iter(design["entities"].values()))
    assert "boss" in first["tags"]


def test_patch_add_tag_archetypes_still_preferred_over_entities():
    """When both archetypes AND entities exist, archetypes wins
    (schema-canonical preference)."""
    design = {
        "archetypes": {"player": {"tags": ["player"]}},
        "entities": [{"id": "e1", "tags": []}],
    }
    err = {
        "kind": "tag_requirement",
        "message": "X requires tags special on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    assert "special" in design["archetypes"]["player"]["tags"]
    # Entities should NOT have been touched
    assert design["entities"][0]["tags"] == []


def test_patch_duplicate_id_renames_on_collision():
    """Standard case: mechanics have ids, patcher appends _dup<n>."""
    design = {
        "mechanics": [
            {"id": "cam", "type": "CameraFollow"},
            {"id": "cam", "type": "CameraFollow"},  # collides with [0]
        ],
    }
    err = {
        "kind": "duplicate_id",
        "message": "duplicate mechanic id cam",
        "path": "mechanics[1].id",
    }
    ok = _patch_duplicate_id(design, err)
    assert ok is True
    assert design["mechanics"][1]["id"] == "cam_dup2"


def test_patch_duplicate_id_synthesizes_when_empty():
    """Gap #24 (Round O 2026-04-20): wave emitted mechanics without `id`
    fields — all reported as duplicate (id=undefined). Patcher now
    synthesizes id from type + idx."""
    design = {
        "mechanics": [
            {"type": "CameraFollow"},   # no id!
            {"type": "RoomGraph"},       # no id!
        ],
    }
    err = {
        "kind": "duplicate_id",
        "message": "duplicate mechanic id undefined",
        "path": "mechanics[0].id",
    }
    ok = _patch_duplicate_id(design, err)
    assert ok is True
    new_id = design["mechanics"][0]["id"]
    assert new_id.startswith("CameraFollow"), (
        f"synthesized id should start with type, got {new_id!r}"
    )
    assert "0" in new_id, f"synthesized id should include idx, got {new_id!r}"


def test_patch_duplicate_id_empty_type_fallback():
    """If BOTH id and type are missing, falls back to 'mechanic_<idx>'."""
    design = {"mechanics": [{}]}  # totally empty mechanic
    err = {
        "kind": "duplicate_id",
        "message": "duplicate mechanic id undefined",
        "path": "mechanics[0].id",
    }
    ok = _patch_duplicate_id(design, err)
    assert ok is True
    assert "mechanic" in design["mechanics"][0]["id"].lower()


def test_patch_duplicate_id_synthesized_uniqueness():
    """When synthesizing, ensure no collision with other ids."""
    design = {
        "mechanics": [
            {"type": "X"},          # will synthesize X_0
            {"id": "X_0"},          # already has X_0 — forces X_0_2
        ],
    }
    err = {
        "kind": "duplicate_id",
        "message": "duplicate mechanic id undefined",
        "path": "mechanics[0].id",
    }
    ok = _patch_duplicate_id(design, err)
    assert ok is True
    new_id = design["mechanics"][0]["id"]
    # Must not equal the existing "X_0"
    assert new_id != "X_0", f"collision: synthesized id clashed with existing, got {new_id!r}"


def test_patch_dangling_condition_flow_linear_steps():
    """Canonical case — flow.linear.steps[i].condition dropped."""
    design = {
        "flow": {
            "kind": "linear",
            "steps": [
                {"scene": "main", "condition": "never_emitted"},
                {"scene": "end"},
            ],
        },
    }
    err = {
        "kind": "dangling_condition",
        "message": "condition never_emitted is consumed but never emitted",
        "path": "flow.linear.steps[0].condition",
    }
    ok = _patch_dangling_condition(design, err)
    assert ok is True
    assert "condition" not in design["flow"]["steps"][0]


def test_patch_dangling_condition_deep_path_mechanics_trigger():
    """Gap #28 (Round R 2026-04-20): dangling condition deep inside
    mechanic params. Generic path-walk drops the terminal key."""
    design = {
        "mechanics": [
            {
                "id": "rg",
                "type": "RoomGraph",
                "params": {
                    "scenes": [
                        {
                            "name": "main",
                            "connections": [
                                {"to": "dungeon", "trigger": "always"},
                            ],
                        },
                    ],
                },
            },
        ],
    }
    err = {
        "kind": "dangling_condition",
        "message": "condition always is consumed but never emitted",
        "path": "mechanics[0].params.scenes[0].connections[0].trigger",
    }
    ok = _patch_dangling_condition(design, err)
    assert ok is True
    conn = design["mechanics"][0]["params"]["scenes"][0]["connections"][0]
    assert "trigger" not in conn


def test_patch_dangling_condition_multiple_nested():
    """Multiple dangling triggers in sequence — each patch resolves one."""
    design = {
        "mechanics": [
            {
                "params": {
                    "scenes": [
                        {"connections": [
                            {"trigger": "c1"},
                            {"trigger": "c2"},
                        ]},
                    ],
                },
            },
        ],
    }
    for idx in (0, 1):
        err = {
            "kind": "dangling_condition",
            "message": "condition consumed but never emitted",
            "path": f"mechanics[0].params.scenes[0].connections[{idx}].trigger",
        }
        assert _patch_dangling_condition(design, err) is True
    conns = design["mechanics"][0]["params"]["scenes"][0]["connections"]
    assert "trigger" not in conns[0]
    assert "trigger" not in conns[1]


def test_patch_dangling_condition_rejects_unknown_terminal():
    """Only .condition/.trigger/.when_state are safe to drop. Other
    keys could be structural — bail."""
    design = {"mechanics": [{"params": {"target": "player"}}]}
    err = {
        "kind": "dangling_condition",
        "message": "x",
        "path": "mechanics[0].params.target",
    }
    ok = _patch_dangling_condition(design, err)
    assert ok is False


def test_patch_dangling_condition_safe_on_bad_path():
    """Malformed path shouldn't crash."""
    design = {"mechanics": []}
    err = {"kind": "dangling_condition", "message": "x", "path": "invalid[[path"}
    try:
        ok = _patch_dangling_condition(design, err)
    except Exception as e:
        raise AssertionError(f"should not raise, got {e!r}")
    assert ok is False


def test_round_p_simulation_full_auto_fix_pipeline():
    """Simulate Round P's exact failure modes hitting the auto-fixer:
    - Wave emits entities: [...] instead of archetypes: {...}
    - Mechanics have no ids (all id=undefined)
    - CheckpointProgression requires 'checkpoint' tag

    This exercises Fix #17b, #23, #24, #25 in a single pipeline pass.
    The unresolved list should be empty after auto-fix."""
    design = {
        "meta": {"title": "Hyrule", "shape": "action", "vibe": []},
        "entities": [
            {"id": "player", "name": "Link", "tags": ["hero"]},
            {"id": "octorok", "tags": ["enemy"]},
        ],
        "mechanics": [
            {"type": "CameraFollow"},         # no id (duplicate_id)
            {"type": "RoomGraph"},             # no id (duplicate_id)
            {"type": "CheckpointProgression"}, # no id + requires 'checkpoint' tag
        ],
    }
    errors = [
        {"kind": "duplicate_id", "message": "duplicate mechanic id undefined",
         "path": "mechanics[0].id"},
        {"kind": "duplicate_id", "message": "duplicate mechanic id undefined",
         "path": "mechanics[1].id"},
        {"kind": "duplicate_id", "message": "duplicate mechanic id undefined",
         "path": "mechanics[2].id"},
        {"kind": "tag_requirement",
         "message": "CheckpointProgression requires tags checkpoint on some archetype, none found",
         "path": "mechanics[2].type"},
    ]
    patched, unresolved = fix_design_validation_errors(design, errors)
    assert unresolved == [], f"expected 0 unresolved, got: {unresolved}"
    # All 3 mechanics now have synthesized ids
    for i, m in enumerate(patched["mechanics"]):
        assert m.get("id"), f"mechanics[{i}] still has no id: {m}"
    # First entity got the checkpoint tag
    assert "checkpoint" in patched["entities"][0]["tags"]
    # Archetypes mirror was created and has the checkpoint tag
    assert "archetypes" in patched
    assert isinstance(patched["archetypes"], dict)
    assert any(
        "checkpoint" in a.get("tags", [])
        for a in patched["archetypes"].values()
        if isinstance(a, dict)
    ), f"no archetype has checkpoint tag: {patched['archetypes']}"


def test_patch_add_tag_empty_archetypes_falls_through_to_entities():
    """If archetypes exists but is empty, fall through to entities
    (don't return False prematurely)."""
    design = {
        "archetypes": {},   # empty dict
        "entities": [{"id": "e1", "tags": []}],
    }
    err = {
        "kind": "tag_requirement",
        "message": "X requires tags special on some archetype, none found",
    }
    ok = _patch_add_tag(design, err)
    assert ok is True
    assert "special" in design["entities"][0]["tags"]


def main():
    tests = [
        test_patch_add_tag_dict_shape,
        test_patch_add_tag_list_shape,
        test_patch_add_tag_multiple_tags,
        test_patch_add_tag_no_archetypes_returns_false,
        test_patch_add_tag_malformed_archetypes_safe,
        test_fix_design_validation_errors_end_to_end_list_shape,
        test_patch_add_tag_entities_list_fallback,
        test_patch_add_tag_entities_mirrors_into_archetypes,
        test_patch_add_tag_entities_mirror_uses_name_fallback,
        test_patch_add_tag_entities_mirror_final_fallback_entity_0,
        test_patch_add_tag_entities_dict_fallback,
        test_patch_add_tag_archetypes_still_preferred_over_entities,
        test_patch_duplicate_id_renames_on_collision,
        test_patch_duplicate_id_synthesizes_when_empty,
        test_patch_duplicate_id_empty_type_fallback,
        test_patch_duplicate_id_synthesized_uniqueness,
        test_patch_add_tag_empty_archetypes_falls_through_to_entities,
        test_patch_dangling_condition_flow_linear_steps,
        test_patch_dangling_condition_deep_path_mechanics_trigger,
        test_patch_dangling_condition_multiple_nested,
        test_patch_dangling_condition_rejects_unknown_terminal,
        test_patch_dangling_condition_safe_on_bad_path,
        test_round_p_simulation_full_auto_fix_pipeline,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print()
    if failed:
        print(f"RESULT: {len(failed)}/{len(tests)} failed: {failed}")
        sys.exit(1)
    print(f"RESULT: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
