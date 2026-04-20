"""Tests for project_init_gamedev — Phase 9 wiring.

Verifies:
- Genre scaffold directories exist on disk (fighting / action_adventure /
  custom / cross/magic_hoops).
- _resolve_genre maps canonical + alias names to the right subdir.
- _rewrite_engine_paths collapses 2/3/4-level engine refs to 1-level.
- End-to-end: copying scaffold into a tempdir yields a deliverable
  with rewritten paths and no stale `../../engine` references.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.tools.project_init_gamedev import (  # noqa: E402
    _GENRE_MAP,
    _list_customization_files,
    _resolve_genre,
    _rewrite_engine_paths,
    GAMEDEV_DIR,
    ENGINE_DIR,
)


# ---- scaffolds on disk ----

class TestScaffoldsOnDisk:
    def test_gamedev_root_exists(self):
        assert GAMEDEV_DIR.is_dir(), f"missing {GAMEDEV_DIR}"

    def test_engine_root_exists(self):
        assert ENGINE_DIR.is_dir(), f"missing {ENGINE_DIR}"

    @pytest.mark.parametrize("sub", ["custom", "action_adventure", "fighting", "jrpg", "platformer", "fps", "stealth", "racing", "cross/magic_hoops", "cross/ninja_garden", "cross/rhythm_fighter"])
    def test_genre_dir_exists(self, sub):
        d = GAMEDEV_DIR / sub
        assert d.is_dir(), f"missing scaffold dir {d}"
        assert (d / "package.json").exists()
        assert (d / "tsconfig.json").exists()


# ---- genre resolution ----

class TestResolveGenre:
    def test_canonical_names(self):
        assert _resolve_genre("custom") == "custom"
        assert _resolve_genre("action_adventure") == "action_adventure"
        assert _resolve_genre("fighting") == "fighting"
        assert _resolve_genre("jrpg") == "jrpg"
        assert _resolve_genre("platformer") == "platformer"
        assert _resolve_genre("fps") == "fps"
        assert _resolve_genre("stealth") == "stealth"
        assert _resolve_genre("racing") == "racing"
        assert _resolve_genre("magic_hoops") == "cross/magic_hoops"
        assert _resolve_genre("ninja_garden") == "cross/ninja_garden"
        assert _resolve_genre("rhythm_fighter") == "cross/rhythm_fighter"

    def test_aliases(self):
        assert _resolve_genre("action-adventure") == "action_adventure"
        assert _resolve_genre("adventure") == "action_adventure"
        assert _resolve_genre("fighter") == "fighting"
        assert _resolve_genre("brawler") == "fighting"
        assert _resolve_genre("rpg") == "jrpg"
        assert _resolve_genre("final-fantasy") == "jrpg"
        assert _resolve_genre("mario") == "platformer"
        assert _resolve_genre("celeste") == "platformer"
        assert _resolve_genre("doom") == "fps"
        assert _resolve_genre("first-person-shooter") == "fps"
        assert _resolve_genre("metal-gear") == "stealth"
        assert _resolve_genre("sneak") == "stealth"
        assert _resolve_genre("kart") == "racing"
        assert _resolve_genre("mario-kart") == "racing"
        assert _resolve_genre("gran-turismo") == "racing"
        assert _resolve_genre("terraria") == "cross/ninja_garden"
        assert _resolve_genre("ninja-gaiden") == "cross/ninja_garden"
        assert _resolve_genre("rhythm-fighter") == "cross/rhythm_fighter"
        assert _resolve_genre("parappa-fighter") == "cross/rhythm_fighter"
        assert _resolve_genre("cross-genre") == "cross/magic_hoops"
        assert _resolve_genre("canary") == "cross/magic_hoops"

    def test_case_insensitive(self):
        assert _resolve_genre("FIGHTING") == "fighting"
        assert _resolve_genre("Action_Adventure") == "action_adventure"

    def test_space_to_underscore(self):
        assert _resolve_genre("magic hoops") == "cross/magic_hoops"

    def test_unknown_returns_empty(self):
        assert _resolve_genre("cobra-kai") == ""
        assert _resolve_genre("rts") == ""

    def test_empty_defaults_to_custom(self):
        assert _resolve_genre("") == "custom"
        assert _resolve_genre("generic") == "custom"

    def test_genre_map_targets_real_dirs(self):
        seen = set()
        for _alias, sub in _GENRE_MAP.items():
            if not sub:
                continue
            if sub in seen:
                continue
            seen.add(sub)
            assert (GAMEDEV_DIR / sub).is_dir(), f"_GENRE_MAP points to missing {sub}"


# ---- path rewriting ----

class TestRewriteEnginePaths:
    def _scratch(self, suffix: str = ""):
        d = Path(tempfile.mkdtemp(prefix="gamedev_rewrite_test_")) / ("proj" + suffix)
        d.mkdir(parents=True)
        return d

    def test_two_level_collapses(self):
        d = self._scratch()
        (d / "tsconfig.json").write_text(json.dumps({
            "compilerOptions": {
                "paths": {
                    "@engine":   ["../../engine/src/index"],
                    "@engine/*": ["../../engine/src/*"],
                }
            }
        }))
        _rewrite_engine_paths(d)
        text = (d / "tsconfig.json").read_text()
        assert "../../engine" not in text
        assert "../engine/src/index" in text
        assert "../engine/src/*" in text
        shutil.rmtree(d.parent)

    def test_three_level_collapses(self):
        d = self._scratch()
        (d / "tsconfig.json").write_text(json.dumps({
            "compilerOptions": {
                "paths": {
                    "@engine":   ["../../../engine/src/index"],
                    "@engine/*": ["../../../engine/src/*"],
                }
            }
        }))
        _rewrite_engine_paths(d)
        text = (d / "tsconfig.json").read_text()
        assert "../../../engine" not in text
        assert "../../engine" not in text
        assert "../engine/src/index" in text

    def test_package_json_engine_dep(self):
        d = self._scratch()
        (d / "package.json").write_text(json.dumps({
            "name": "x",
            "dependencies": {"engine": "file:../../engine"},
        }))
        _rewrite_engine_paths(d)
        pkg = json.loads((d / "package.json").read_text())
        assert pkg["dependencies"]["engine"] == "file:../engine"

    def test_missing_files_noop(self):
        d = self._scratch()
        # No crash on missing tsconfig/package.json.
        _rewrite_engine_paths(d)


# ---- end-to-end scaffold copy ----

class TestEndToEndCopy:
    """Dry-run the copy+rewrite steps without calling `npm install` or
    starting a dev server. Proves the deliverable is path-correct."""

    @pytest.mark.parametrize("genre,expected_sub", [
        ("custom", "custom"),
        ("action_adventure", "action_adventure"),
        ("fighting", "fighting"),
        ("jrpg", "jrpg"),
        ("platformer", "platformer"),
        ("fps", "fps"),
        ("stealth", "stealth"),
        ("racing", "racing"),
        ("magic_hoops", "cross/magic_hoops"),
        ("ninja_garden", "cross/ninja_garden"),
        ("rhythm_fighter", "cross/rhythm_fighter"),
    ])
    def test_copy_and_rewrite(self, genre, expected_sub):
        sub = _resolve_genre(genre)
        assert sub == expected_sub

        src = GAMEDEV_DIR / sub
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "deliverables" / "test_proj"
            shutil.copytree(
                src, dst,
                ignore=shutil.ignore_patterns(
                    "node_modules", "dist", ".vite", "package-lock.json"
                ),
            )
            _rewrite_engine_paths(dst)

            ts = (dst / "tsconfig.json").read_text()
            pkg_text = (dst / "package.json").read_text()

            # After rewrite, no multi-level engine ref should survive.
            assert "../../engine" not in ts
            assert "../../../engine" not in ts
            assert "../../engine" not in pkg_text
            assert "../../../engine" not in pkg_text

            # One-level ref must be present so the sibling symlink works.
            assert "../engine" in ts or "../engine" in pkg_text


# ---- customization file listing ----

class TestCustomizationSurface:
    def test_fighting_lists_data_files(self):
        files = _list_customization_files(GAMEDEV_DIR / "fighting")
        assert any(f.startswith("data/") for f in files)
        assert any("scenes" in f for f in files)
        assert "src/main.ts" in files

    def test_action_adventure_lists_data_files(self):
        files = _list_customization_files(GAMEDEV_DIR / "action_adventure")
        assert any(f.startswith("data/") for f in files)
        assert any("scenes" in f for f in files)

    def test_magic_hoops_lists_data_files(self):
        files = _list_customization_files(GAMEDEV_DIR / "cross" / "magic_hoops")
        assert any(f.startswith("data/") for f in files)
        assert any("Match.ts" in f for f in files)
