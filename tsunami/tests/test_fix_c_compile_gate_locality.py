"""FIX-C (JOB-INT-12) — Swell compile-gate error-locality classifier.

Tests the inline `_is_framework` classifier at agent.py:5438+ that
partitions compile-gate errors by path prefix before feeding them to
the drone's system_note. Framework errors (../engine/, engine/src/)
are drone-non-fixable; project errors (deliverables/<project>/) are.
"""
from __future__ import annotations


def _is_framework(ln: str) -> bool:
    """Mirror of the inline classifier in agent.py:5438. Kept here as a
    duplicate to test without ctor-spinning an Agent. If the rule moves
    into a helper module, this import should update — but the contract
    matters, not the call-site."""
    return ("../engine/" in ln or "engine/src/" in ln
            or "../../engine" in ln)


def test_engine_relative_path_classified_as_framework():
    ln = "../engine/src/design/mechanics/equipment_loadout.ts(129,69): error TS2345: Argument of type 'null' is not assignable to parameter of type 'WorldFlagValue'."
    assert _is_framework(ln)


def test_engine_src_absolute_classified_as_framework():
    ln = "/home/jb/ark/scaffolds/engine/src/foo.ts(5,5): error TS2339: Property does not exist."
    assert _is_framework(ln)


def test_double_relative_engine_classified_as_framework():
    ln = "../../engine/src/design/bar.ts(10,10): error TS1234"
    assert _is_framework(ln)


def test_project_deliverable_path_not_framework():
    ln = "src/scenes/Stage.ts(42,10): error TS2345: something wrong"
    assert not _is_framework(ln)


def test_project_data_path_not_framework():
    ln = "data/characters.json(1,1): error: trailing comma"
    assert not _is_framework(ln)


def test_empty_line_not_framework():
    assert not _is_framework("")


def test_generic_error_not_framework():
    ln = "Error: something broke in the universe"
    assert not _is_framework(ln)


def test_mixed_partitioning_shape():
    """Smoke test that 3 framework + 2 project partition as expected."""
    lines = [
        "../engine/src/design/mechanics/x.ts(1,1): error TS1",
        "engine/src/game/y.ts(2,2): error TS2",
        "../../engine/tsconfig.json(3,3): error TS3",
        "src/scenes/Title.ts(4,4): error TS4",
        "data/config.json(5,5): error: bad json",
    ]
    framework = [l for l in lines if _is_framework(l)]
    project = [l for l in lines if not _is_framework(l)]
    assert len(framework) == 3
    assert len(project) == 2
