"""Scaffold-first delivery gate — JOB-INT-6 tests.

Verifies that the gamedev branch of `code_write_gate` accepts a
scaffold-first delivery (customized `data/*.json`) as success,
without needing a legacy `emit_design`-produced
`game_definition.json`.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import sys
REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.deliver_gates import (  # noqa: E402
    code_write_gate,
    _scaffold_first_modifications,
    _SCAFFOLD_ROOT,
)


def _make_fake_project(tmpdir: Path, genre: str, mods: dict[str, dict]) -> Path:
    """Mirror a genre's seed into a fake project_dir, optionally
    overwriting specific files with custom content."""
    seed_dir = _SCAFFOLD_ROOT / genre / "data"
    project_dir = tmpdir / "fake_project"
    (project_dir / "data").mkdir(parents=True)
    for f in seed_dir.glob("*.json"):
        dest = project_dir / "data" / f.name
        if f.name in mods:
            dest.write_text(json.dumps(mods[f.name], indent=2))
        else:
            dest.write_bytes(f.read_bytes())
    return project_dir


def test_unmodified_scaffold_fails():
    """Drone copied the scaffold but customized nothing → gate FAILS."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = _make_fake_project(tmp, "action_adventure", mods={})
        result = code_write_gate(
            state_flags={
                "target_scaffold": "gamedev",
                "target_genre": "action_adventure",
            },
            project_dir=proj,
        )
        assert not result.passed, "Unmodified scaffold must not pass"
        assert ("no" in result.message.lower()
                or "not" in result.message.lower()
                or "neither" in result.message.lower())


def test_modified_entities_passes():
    """Drone customized data/entities.json → gate PASSES via scaffold-first."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = _make_fake_project(tmp, "action_adventure", mods={
            "entities.json": {
                "archetypes": {
                    "custom_enemy": {"mesh": "capsule", "tags": ["enemy"]},
                },
            },
        })
        result = code_write_gate(
            state_flags={
                "target_scaffold": "gamedev",
                "target_genre": "action_adventure",
            },
            project_dir=proj,
        )
        assert result.passed, f"Modified scaffold must pass, got: {result.message}"
        assert "scaffold-first" in result.message


def test_legacy_game_definition_still_passes():
    """Legacy emit_design path still works — game_definition.json present."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = tmp / "legacy_project"
        (proj / "public").mkdir(parents=True)
        (proj / "public" / "game_definition.json").write_text("{}")
        result = code_write_gate(
            state_flags={
                "target_scaffold": "gamedev",
                "target_genre": "action_adventure",  # irrelevant for legacy
            },
            project_dir=proj,
        )
        assert result.passed
        assert "game_definition.json" in result.message


def test_helper_detects_new_file():
    """A file that isn't in the seed is still treated as a customization."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = _make_fake_project(tmp, "platformer", mods={})
        # Add a brand-new file to project's data/ that isn't in seed
        (proj / "data" / "custom_levels.json").write_text("{}")
        modified = _scaffold_first_modifications(proj, "platformer")
        assert "custom_levels.json" in modified


def test_genre_alias_resolves_to_scaffold_dir():
    """pick_genre returns signal names like 'fighter' or 'kart_racer' —
    the scaffold dirs are 'fighting' / 'racing'. Helper must resolve
    via project_init_gamedev._GENRE_MAP so the gate doesn't miss real
    customizations under the alias name."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = _make_fake_project(tmp, "fighting", mods={
            "characters.json": {"characters": {"custom-fighter": {}}},
        })
        # Pass the SIGNAL name, not the dir name
        result = code_write_gate(
            state_flags={
                "target_scaffold": "gamedev",
                "target_genre": "fighter",  # signal, not dir
            },
            project_dir=proj,
        )
        assert result.passed, f"alias 'fighter' must resolve to 'fighting', got: {result.message}"
        assert "scaffold-first" in result.message


def test_helper_empty_on_unknown_genre():
    """Unknown genre → no seed dir → helper safely returns empty."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = tmp / "unknown_project"
        (proj / "data").mkdir(parents=True)
        (proj / "data" / "enemies.json").write_text("{}")
        modified = _scaffold_first_modifications(proj, "nonexistent_genre_xyz")
        assert modified == []


def test_missing_genre_flag_skips_scaffold_first_check():
    """If target_genre isn't set, the scaffold-first branch is skipped
    cleanly and the legacy behavior wins (or fails with the combined
    message)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = _make_fake_project(tmp, "action_adventure", mods={
            "entities.json": {"archetypes": {"custom": {}}},
        })
        # NO target_genre
        result = code_write_gate(
            state_flags={"target_scaffold": "gamedev"},
            project_dir=proj,
        )
        # Without genre, scaffold-first check is skipped — fail message
        # still mentions scaffold-first as one of the paths, but
        # passed=False is the real assertion.
        assert not result.passed
