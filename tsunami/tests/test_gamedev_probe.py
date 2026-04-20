"""Tests for core/gamedev_probe — catalog composition + game_def shape.

Fix #6: registers gamedev_probe in the core/dispatch _PROBES map so
delivery-gate calls for scaffold=gamedev reach this probe instead of
falling back to no-op.
Fix #18: probe reads archetypes union entities (schema-canonical +
legacy shape support).
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.core.gamedev_probe import gamedev_probe  # noqa: E402
from tsunami.core.dispatch import _PROBES             # noqa: E402


def _setup(tmp: Path, game_def: dict | None) -> Path:
    public = tmp / "public"
    public.mkdir(parents=True)
    if game_def is not None:
        (public / "game_definition.json").write_text(json.dumps(game_def))
    return tmp


def test_dispatch_map_has_gamedev():
    # The gamedev entry now points at the routing dispatcher — it picks
    # between gamedev_probe (legacy) and gamedev_scaffold_probe (new)
    # based on on-disk markers. The legacy probe stays reachable via
    # _gamedev_probe_legacy for direct-dispatch callers.
    from tsunami.core.dispatch import _gamedev_probe_legacy
    from tsunami.core.gamedev_scaffold_probe import gamedev_probe_dispatch
    assert "gamedev" in _PROBES
    assert _PROBES["gamedev"] is gamedev_probe_dispatch
    assert _gamedev_probe_legacy is gamedev_probe


def test_no_game_def_fails():
    with tempfile.TemporaryDirectory() as td:
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is False
        assert "NO game_definition.json" in r["issues"]


def test_malformed_json_fails():
    with tempfile.TemporaryDirectory() as td:
        pub = Path(td) / "public"
        pub.mkdir()
        (pub / "game_definition.json").write_text("{not valid json")
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is False
        assert "not valid JSON" in r["issues"]


def test_empty_structure_fails():
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {"scenes": [], "entities": [], "mechanics": []})
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is False
        assert "no scenes" in r["issues"] or "no entities" in r["issues"]


def test_unknown_mechanics_flagged():
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": [{"name": "main"}],
            "entities": [{"name": "player"}],
            "mechanics": [
                {"type": "CameraFollow", "params": {}},
                {"type": "WarpDriveReverser", "params": {}},  # invented
                {"type": "QuantumFluxCapacitor", "params": {}},  # invented
            ],
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is False
        assert "unknown type" in r["issues"]
        assert "WarpDriveReverser" in r["issues"]


def test_zero_catalog_composition_flagged():
    """Every mechanic is invented — catches the 'wave re-implemented
    primitives' failure mode."""
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": [{"name": "main"}],
            "entities": [{"name": "player"}],
            "mechanics": [{"type": "Invented1"}, {"type": "Invented2"}],
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is False
        assert ("0 of 2 mechanics" in r["issues"]
                or "not composing" in r["issues"])


def test_valid_composition_passes():
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": [{"name": "main"}, {"name": "dungeon_1"}],
            "entities": [{"name": "player"}, {"name": "octorok"}],
            "mechanics": [
                {"type": "CameraFollow", "params": {"target": "player"}},
                {"type": "RoomGraph", "params": {"scenes": ["main", "dungeon_1"]}},
                {"type": "LockAndKey", "params": {"keys": ["dungeon_key"]}},
                {"type": "HUD", "params": {}},
                {"type": "ItemUse", "params": {}},
                {"type": "PickupLoop", "params": {}},
            ],
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is True, f"failed: {r['issues']}"
        # raw summary includes catalog_mechanics count
        assert "catalog_mechanics=6" in r["raw"]


def test_game_def_at_project_root_fallback():
    """Some builds emit at project root, not public/."""
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "game_definition.json").write_text(json.dumps({
            "scenes": [{"name": "main"}],
            "entities": [{"name": "p"}],
            "mechanics": [{"type": "HUD"}],
        }))
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is True


def test_compiled_dict_scenes_shape_accepted():
    """Compiled game_definition.json has scenes as a Record<string,Scene>
    (dict keyed by scene name), entities nested inside each scene as a
    list. Round G landed a real delivery in this shape and the probe
    used to reject it with 'no scenes[]' — false negative."""
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": {
                "main": {
                    "name": "main",
                    "entities": [
                        {"id": "player", "tags": ["player"]},
                        {"id": "goomba1", "tags": ["enemy"]},
                    ],
                },
                "gameover": {"name": "gameover", "entities": []},
            },
            "mechanics": [
                {"id": "cam", "type": "CameraFollow"},
                {"id": "rg", "type": "RoomGraph"},
            ],
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is True, f"failed: {r['issues']}"
        # raw summary correctly counts scenes and entities (entities
        # collected from scene.entities in compiled form)
        assert "scenes=2" in r["raw"]
        assert "entities=2" in r["raw"]


def test_compiled_shape_empty_entities_still_fails():
    """Round G's exact deliverable shape — scenes dict with main scene
    but entities=[] inside — must fail the probe, not pass."""
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": {"main": {"name": "main", "entities": []}},
            "mechanics": [{"id": "cam", "type": "CameraFollow"}],
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is False
        assert "no entities" in r["issues"]


def test_mechanics_as_dict_record_shape_accepted():
    """Input DesignScript can have mechanics as Record<string,Mechanic>.
    Probe must handle both dict and list shapes."""
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": [{"name": "main"}],
            "entities": [{"name": "player"}],
            "mechanics": {
                "cam": {"type": "CameraFollow"},
                "rg": {"type": "RoomGraph"},
            },
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is True, f"failed: {r['issues']}"
        assert "mechanics=2" in r["raw"]
        assert "catalog_mechanics=2" in r["raw"]


def test_archetypes_dict_shape_accepted_as_entities():
    """Gap #18 (Round M-forward): schema-canonical shape uses
    `archetypes: {}` at root instead of `entities: []`. Probe must
    count archetypes values as entities so well-formed schema-canonical
    deliveries don't get flagged 'no entities' falsely."""
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": [{"name": "main"}],
            "archetypes": {
                "player": {"tags": ["player"], "components": ["Health(4)"]},
                "octorok": {"tags": ["enemy"], "components": ["Health(1)"]},
            },
            "mechanics": [{"id": "cam", "type": "CameraFollow"}],
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is True, f"failed: {r['issues']}"
        assert "entities=2" in r["raw"]


def test_archetypes_list_shape_accepted_as_entities():
    """Round L iter 7 drift: wave emits archetypes as list-of-objects
    instead of dict. Probe must still count them as entities (gap #18)."""
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": [{"name": "main"}],
            "archetypes": [
                {"id": "player", "tags": ["player"]},
                {"id": "goomba", "tags": ["enemy"]},
            ],
            "mechanics": [{"id": "cam", "type": "CameraFollow"}],
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is True, f"failed: {r['issues']}"
        assert "entities=2" in r["raw"]


def test_archetypes_and_entities_coexist_are_unioned():
    """Hybrid delivery — some archetypes, some legacy entities.
    Probe should union them (additive), not pick one and ignore the other."""
    with tempfile.TemporaryDirectory() as td:
        _setup(Path(td), {
            "scenes": [{"name": "main"}],
            "archetypes": {"player": {"tags": ["player"]}},
            "entities": [{"name": "pickup_rupee"}],
            "mechanics": [{"id": "cam", "type": "CameraFollow"}],
        })
        r = asyncio.run(gamedev_probe(Path(td)))
        assert r["passed"] is True, f"failed: {r['issues']}"
        assert "entities=2" in r["raw"]


def main():
    tests = [
        test_dispatch_map_has_gamedev,
        test_no_game_def_fails,
        test_malformed_json_fails,
        test_empty_structure_fails,
        test_unknown_mechanics_flagged,
        test_zero_catalog_composition_flagged,
        test_valid_composition_passes,
        test_game_def_at_project_root_fallback,
        test_compiled_dict_scenes_shape_accepted,
        test_compiled_shape_empty_entities_still_fails,
        test_mechanics_as_dict_record_shape_accepted,
        test_archetypes_dict_shape_accepted_as_entities,
        test_archetypes_list_shape_accepted_as_entities,
        test_archetypes_and_entities_coexist_are_unioned,
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
