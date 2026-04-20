"""Gap #26 (Round Q 2026-04-20): emit_design pre-compile shape normalizer.

Round Q ran a wave with all Fixes #1-25 active. Iter 6 emit_design
succeeded on first try (no validation errors, no auto-fix needed).
BUT the compiled game_definition.json was nearly empty — 1.2KB of
default skeleton with 0 entities, despite the wave emitting a rich
design with 9+ Zelda enemies (Link, Octorok, Moblin, Keese, ...).

Root cause: the wave emits `entities: [...]` at root but the engine
compiler reads `archetypes: {...}` only. With no shape error from the
validator, the compiler silently drops the entities array and
substitutes defaults. emit_design returns ok=true with a functionally-
empty deliverable.

Fix #26: pre-compile shape lifter — if design has `entities` but no
`archetypes`, lift entities → archetypes (dict keyed by id/name/idx).
Runs before subprocess.run so the compiler sees the right shape.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))


def _lift_components_from_params(ent: dict) -> list:
    comps = list(ent.get("components", []) or [])
    params = ent.get("params", {}) if isinstance(ent.get("params"), dict) else {}
    src = {**ent, **params}
    has_health = any(c.startswith("Health(") for c in comps)
    if "hp" in src and isinstance(src["hp"], (int, float)) and not has_health:
        comps.append(f"Health({int(src['hp'])})")
        has_health = True
    if "max_hp" in src and isinstance(src["max_hp"], (int, float)) and not has_health:
        comps.append(f"Health({int(src['max_hp'])})")
    if "score" in src and not any(c == "Score" for c in comps):
        comps.append("Score")
    if src.get("inventory") is True or "items" in src:
        if not any(c == "Inventory" for c in comps):
            comps.append("Inventory")
    return comps


def _ent_tags_with_name(ent: dict) -> list:
    tags = list(ent.get("tags", []) or [])
    name = ent.get("name")
    if isinstance(name, str) and name.strip():
        if name not in tags:
            tags.append(name)
    return tags


def _simulate_lift(design_obj: dict) -> dict:
    """Mirror the logic of emit_design.py's Fix #26 block — tests
    the BEHAVIOR not the specific function. If emit_design moves the
    lift logic, update this mirror."""
    if not isinstance(design_obj, dict):
        return design_obj
    if design_obj.get("entities") and not design_obj.get("archetypes"):
        ents = design_obj["entities"]
        lifted: dict = {}
        if isinstance(ents, list):
            for idx, ent in enumerate(ents):
                if not isinstance(ent, dict):
                    continue
                aid = (ent.get("id") or ent.get("name") or f"entity_{idx}")
                if aid in lifted:
                    aid = f"{aid}_{idx}"
                arch = {
                    "tags": _ent_tags_with_name(ent),
                    "components": _lift_components_from_params(ent),
                }
                for k in ("mesh", "controller", "ai", "trigger", "sprite_ref"):
                    if k in ent:
                        arch[k] = ent[k]
                lifted[aid] = arch
        elif isinstance(ents, dict):
            for eid, ent in ents.items():
                if not isinstance(ent, dict):
                    continue
                arch = {
                    "tags": _ent_tags_with_name(ent),
                    "components": _lift_components_from_params(ent),
                }
                for k in ("mesh", "controller", "ai", "trigger", "sprite_ref"):
                    if k in ent:
                        arch[k] = ent[k]
                lifted[eid] = arch
        if lifted:
            design_obj["archetypes"] = lifted
    # Flow normalization
    flow = design_obj.get("flow")
    if isinstance(flow, list) and flow:
        scene_names = [s for s in flow if isinstance(s, str)]
        if scene_names:
            if len(scene_names) == 1:
                design_obj["flow"] = {"kind": "scene", "name": scene_names[0]}
            else:
                design_obj["flow"] = {
                    "kind": "linear",
                    "name": scene_names[0],
                    "steps": [{"scene": s} for s in scene_names],
                }
    return design_obj


def test_lifter_present_in_emit_design():
    """Fix #26 must remain in emit_design.py. Guards against someone
    removing the pre-compile lift by accident."""
    src = (REPO / "tsunami" / "tools" / "emit_design.py").read_text()
    assert "Gap #26" in src, "Fix #26 comment marker missing"
    assert "design_obj.get(\"entities\")" in src or 'design_obj.get("entities")' in src
    assert 'design_obj["archetypes"] = lifted' in src, (
        "pre-compile lift body missing — Fix #26 regressed"
    )


def test_lifter_converts_entities_list_to_archetypes_dict():
    design = {
        "meta": {"title": "Zelda"},
        "entities": [
            {"name": "Link", "tags": ["player"]},
            {"name": "Octorok", "tags": ["enemy"]},
        ],
        "mechanics": [],
    }
    out = _simulate_lift(dict(design))
    assert "archetypes" in out
    assert isinstance(out["archetypes"], dict)
    assert "Link" in out["archetypes"]
    assert "Octorok" in out["archetypes"]
    assert "player" in out["archetypes"]["Link"]["tags"]


def test_lifter_prefers_id_over_name():
    design = {
        "entities": [{"id": "player_1", "name": "Link"}],
    }
    out = _simulate_lift(dict(design))
    assert "player_1" in out["archetypes"]
    assert "Link" not in out["archetypes"]  # id wins


def test_lifter_falls_back_to_entity_idx():
    """Neither id nor name — use entity_<idx>."""
    design = {"entities": [{"tags": []}, {"tags": ["enemy"]}]}
    out = _simulate_lift(dict(design))
    assert "entity_0" in out["archetypes"]
    assert "entity_1" in out["archetypes"]


def test_lifter_handles_duplicate_names():
    """Two entities with the same name — the second gets a suffix."""
    design = {"entities": [{"name": "X"}, {"name": "X"}]}
    out = _simulate_lift(dict(design))
    archs = out["archetypes"]
    # First one keeps "X", second becomes "X_1"
    assert "X" in archs
    assert any(k.startswith("X_") for k in archs.keys() if k != "X")


def test_lifter_preserves_schema_fields():
    """sprite_ref, controller, components etc. should be carried over."""
    design = {
        "entities": [{
            "name": "Link",
            "controller": "topdown",
            "components": ["Health(4)", "Inventory"],
            "sprite_ref": "link_sprite",
            "tags": ["player"],
            # Non-schema fields should NOT carry over unless we explicitly list
            "hp": 4,  # non-schema; OK to drop
        }],
    }
    out = _simulate_lift(dict(design))
    arch = out["archetypes"]["Link"]
    assert arch["controller"] == "topdown"
    assert arch["components"] == ["Health(4)", "Inventory"]
    assert arch["sprite_ref"] == "link_sprite"
    assert "player" in arch["tags"]


def test_lifter_preserves_archetypes_when_already_present():
    """If the wave DID emit archetypes, don't overwrite — respect it."""
    design = {
        "archetypes": {"already": {"tags": ["original"]}},
        "entities": [{"name": "Link"}],
    }
    out = _simulate_lift(dict(design))
    # archetypes should still be the original dict, not lifted from entities
    assert "already" in out["archetypes"]
    assert "Link" not in out["archetypes"]


def test_lifter_handles_entities_as_dict():
    design = {"entities": {"link": {"tags": ["player"]}, "goomba": {"tags": ["enemy"]}}}
    out = _simulate_lift(dict(design))
    assert out["archetypes"]["link"]["tags"] == ["player"]
    assert out["archetypes"]["goomba"]["tags"] == ["enemy"]


def test_lifter_no_op_when_no_entities():
    """No entities, no archetypes → no-op."""
    design = {"meta": {"title": "X"}, "mechanics": []}
    out = _simulate_lift(dict(design))
    assert "archetypes" not in out
    assert "entities" not in out


def test_lifter_translates_hp_to_health_component():
    """Round Q's Link had hp=6 in params. That should surface as
    `Health(6)` in archetype.components so the ComponentSystem picks
    it up at runtime."""
    design = {
        "entities": [{
            "name": "Link",
            "params": {"hp": 6, "maxHp": 6},
        }],
    }
    out = _simulate_lift(dict(design))
    comps = out["archetypes"]["Link"]["components"]
    assert any(c == "Health(6)" for c in comps), f"no Health(6): {comps}"


def test_lifter_translates_top_level_hp_too():
    """Some entities have hp at top level (not nested in params)."""
    design = {"entities": [{"name": "Octorok", "hp": 1}]}
    out = _simulate_lift(dict(design))
    comps = out["archetypes"]["Octorok"]["components"]
    assert any(c == "Health(1)" for c in comps)


def test_lifter_adds_inventory_component_from_items():
    """Entity with `items` array gets Inventory component."""
    design = {
        "entities": [{
            "name": "Link",
            "params": {"items": ["sword", "boomerang"]},
        }],
    }
    out = _simulate_lift(dict(design))
    comps = out["archetypes"]["Link"]["components"]
    assert "Inventory" in comps


def test_lifter_respects_explicit_components():
    """If entity already has components, preserve them and augment."""
    design = {
        "entities": [{
            "name": "X",
            "components": ["CustomThing"],
            "params": {"hp": 3},
        }],
    }
    out = _simulate_lift(dict(design))
    comps = out["archetypes"]["X"]["components"]
    assert "CustomThing" in comps
    assert "Health(3)" in comps


def test_flow_list_with_single_scene_becomes_scene_node():
    """Wave often emits `flow: ["overworld"]` — normalize to
    `flow: {kind: "scene", name: "overworld"}`."""
    design = {"flow": ["overworld"]}
    out = _simulate_lift(dict(design))
    assert isinstance(out["flow"], dict)
    assert out["flow"]["kind"] == "scene"
    assert out["flow"]["name"] == "overworld"


def test_flow_list_multiple_becomes_linear_sequence():
    design = {"flow": ["overworld", "dungeon_1", "boss"]}
    out = _simulate_lift(dict(design))
    assert out["flow"]["kind"] == "linear"
    assert out["flow"]["name"] == "overworld"
    steps = out["flow"]["steps"]
    assert len(steps) == 3
    assert steps[0]["scene"] == "overworld"
    assert steps[2]["scene"] == "boss"


def test_flow_node_object_preserved():
    """If wave already emits a valid FlowNode, don't touch it."""
    design = {"flow": {"kind": "scene", "name": "main", "transition": {"type": "fade"}}}
    original = dict(design["flow"])
    out = _simulate_lift(dict(design))
    # Flow should be unchanged
    assert out["flow"] == original


def test_flow_empty_list_left_alone():
    """Empty list stays empty (degenerate case — schema will error)."""
    design = {"flow": []}
    out = _simulate_lift(dict(design))
    # Not transformed to a FlowNode (no scene names to anchor on)
    assert out["flow"] == []


def test_lifter_preserves_entity_name_as_tag():
    """Gap #30 (Round S post-mortem): wave emits
    {id: 'player_link', name: 'Link'}. Lifter uses id as archetype key
    ('player_link'). 'Link' was lost → probe missed it → undercount.
    Fix #30: preserve name as a tag so it survives compile."""
    design = {
        "entities": [
            {"id": "player_link", "name": "Link", "tags": ["player"]},
            {"id": "enemy_octorok", "name": "Octorok", "tags": ["enemy"]},
        ],
    }
    out = _simulate_lift(dict(design))
    assert "Link" in out["archetypes"]["player_link"]["tags"]
    assert "Octorok" in out["archetypes"]["enemy_octorok"]["tags"]
    # Original tags still there
    assert "player" in out["archetypes"]["player_link"]["tags"]


def test_lifter_name_tag_dedup():
    """If name already present in tags, don't duplicate."""
    design = {
        "entities": [{"id": "p", "name": "Link", "tags": ["Link", "player"]}],
    }
    out = _simulate_lift(dict(design))
    tags = out["archetypes"]["p"]["tags"]
    assert tags.count("Link") == 1


def test_lifter_no_name_no_tag_added():
    """Entity without a name — tags unchanged."""
    design = {"entities": [{"id": "x", "tags": ["enemy"]}]}
    out = _simulate_lift(dict(design))
    assert out["archetypes"]["x"]["tags"] == ["enemy"]


def test_lifter_empty_name_not_added():
    """Blank/whitespace name shouldn't become a tag."""
    design = {"entities": [{"id": "x", "name": "  ", "tags": []}]}
    out = _simulate_lift(dict(design))
    assert out["archetypes"]["x"]["tags"] == []


def test_auto_fix_retry_disables_recursion():
    """The auto-fix retry of emit_design must pass auto_fix=False to
    avoid infinite recursion (validation-error → patch → retry with
    auto_fix enabled → same error path → infinite loop).

    Source-level guard: verify that when emit_design's validation-error
    branch calls itself recursively, auto_fix=False is explicit."""
    import inspect
    from tsunami.tools.emit_design import emit_design as _ed
    src = inspect.getsource(_ed)
    # There's a retry emit_design call inside the validate branch
    assert "retry = emit_design(" in src or "retry=emit_design(" in src, (
        "auto-fix retry call missing"
    )
    # The retry MUST pass auto_fix=False. Look for this exact pattern.
    assert "auto_fix=False" in src, (
        "Fix #8/B-series guard: auto-fix retry must disable recursion. "
        "Without auto_fix=False the validation-error branch recurses "
        "infinitely on persistent validation errors."
    )


def test_round_s_style_wave_output_end_to_end():
    """Simulate Round S's actual emit_design args: 10 canonical Zelda
    names in entities + nested params with hp/items. After the lifter:
    - archetypes dict keyed by each entity's id
    - Each archetype has name in tags (Fix #30)
    - Components translated from hp/items (Fix #26 enhanced)
    - flow list → FlowNode (Fix #26 flow)

    Downstream probe scanning the resulting JSON should find all 10
    canonical names via variant matching (Fix #29)."""
    design = {
        "meta": {"title": "Zelda-like", "shape": "action", "vibe": ["classic"]},
        "entities": [
            {"id": "p_link", "name": "Link", "params": {"hp": 6, "items": ["sword"]}, "tags": ["player"]},
            {"id": "e_octorok", "name": "Octorok", "params": {"hp": 1}, "tags": ["enemy"]},
            {"id": "e_moblin", "name": "Moblin", "params": {"hp": 2}, "tags": ["enemy"]},
            {"id": "e_darknut", "name": "Darknut", "params": {"hp": 4}, "tags": ["enemy"]},
            {"id": "b_aquamentus", "name": "Aquamentus", "params": {"hp": 8}, "tags": ["boss"]},
        ],
        "mechanics": [
            {"id": "cam", "type": "CameraFollow"},
            {"id": "rg", "type": "RoomGraph"},
            {"id": "bp", "type": "BossPhases"},
        ],
        "flow": ["overworld", "dungeon_1"],
    }
    out = _simulate_lift(dict(design))
    # Archetypes exist with preserved names as tags
    assert "archetypes" in out
    archs = out["archetypes"]
    assert "p_link" in archs
    assert "Link" in archs["p_link"]["tags"]
    assert "Aquamentus" in archs["b_aquamentus"]["tags"]
    # Health components lifted from hp
    assert any(c == "Health(6)" for c in archs["p_link"]["components"])
    assert any(c == "Health(8)" for c in archs["b_aquamentus"]["components"])
    # Inventory lifted from items
    assert "Inventory" in archs["p_link"]["components"]
    # Flow normalized to FlowNode (linear with 2 scenes)
    assert isinstance(out["flow"], dict)
    assert out["flow"]["kind"] == "linear"
    assert out["flow"]["name"] == "overworld"
    assert len(out["flow"]["steps"]) == 2
    # Canonical names now ALL survive to the lifted design
    # (probe will match them via variant matching on serialized JSON)
    import json as _j
    serialized = _j.dumps(out)
    for name in ("Link", "Octorok", "Moblin", "Darknut", "Aquamentus"):
        assert name in serialized, f"{name} lost through lift"


def test_lifter_doesnt_duplicate_health_from_max_hp():
    """If both hp AND max_hp present, only add Health() once."""
    design = {
        "entities": [{
            "name": "X",
            "hp": 4, "max_hp": 4,
        }],
    }
    out = _simulate_lift(dict(design))
    comps = out["archetypes"]["X"]["components"]
    health_entries = [c for c in comps if c.startswith("Health(")]
    assert len(health_entries) == 1, f"duplicate Health: {comps}"


def main():
    tests = [
        test_lifter_present_in_emit_design,
        test_lifter_converts_entities_list_to_archetypes_dict,
        test_lifter_prefers_id_over_name,
        test_lifter_falls_back_to_entity_idx,
        test_lifter_handles_duplicate_names,
        test_lifter_preserves_schema_fields,
        test_lifter_preserves_archetypes_when_already_present,
        test_lifter_handles_entities_as_dict,
        test_lifter_no_op_when_no_entities,
        test_lifter_translates_hp_to_health_component,
        test_lifter_translates_top_level_hp_too,
        test_lifter_adds_inventory_component_from_items,
        test_lifter_respects_explicit_components,
        test_flow_list_with_single_scene_becomes_scene_node,
        test_flow_list_multiple_becomes_linear_sequence,
        test_flow_node_object_preserved,
        test_flow_empty_list_left_alone,
        test_lifter_preserves_entity_name_as_tag,
        test_lifter_name_tag_dedup,
        test_lifter_no_name_no_tag_added,
        test_lifter_empty_name_not_added,
        test_lifter_doesnt_duplicate_health_from_max_hp,
        test_auto_fix_retry_disables_recursion,
        test_round_s_style_wave_output_end_to_end,
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
