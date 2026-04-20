"""Tests for tsunami.core.gamedev_scaffold_probe.

Guards:
  - gamedev_scaffold_probe:    data/*.json + scene-wiring + customization
                               checks for the new data-driven flow
  - gamedev_probe_dispatch:    routes between the new probe and the
                               legacy game_definition.json probe based on
                               on-disk markers
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from tsunami.core.gamedev_scaffold_probe import (
    gamedev_probe_dispatch,
    gamedev_scaffold_probe,
)


REPO = Path(__file__).resolve().parent.parent.parent
SEED_ACTION = REPO / "scaffolds" / "gamedev" / "action_adventure"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) \
        if asyncio.get_event_loop_policy()._local._loop else asyncio.run(coro)


def _copy_seed(tmp_path: Path, name: str = "proj") -> Path:
    dst = tmp_path / name
    shutil.copytree(SEED_ACTION, dst)
    return dst


# ---------------------------------------------------------------------------
# scaffold probe
# ---------------------------------------------------------------------------

class TestScaffoldProbeDirect:
    def test_pristine_seed_fails_on_ship_verbatim(self):
        r = asyncio.run(gamedev_scaffold_probe(SEED_ACTION))
        assert r["passed"] is False
        assert "identical" in r["issues"]
        assert "action_adventure" in r["issues"]

    def test_missing_package_json(self, tmp_path):
        r = asyncio.run(gamedev_scaffold_probe(tmp_path))
        assert r["passed"] is False
        assert "package.json" in r["issues"]

    def test_package_without_engine_dep(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "gamedev-custom-scaffold",
            "dependencies": {"react": "*"},
        }))
        r = asyncio.run(gamedev_scaffold_probe(tmp_path))
        assert r["passed"] is False
        assert "engine" in r["issues"]

    def test_empty_data_dir(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "gamedev-custom-scaffold",
            "dependencies": {"engine": "file:../../engine"},
        }))
        (tmp_path / "data").mkdir()
        r = asyncio.run(gamedev_scaffold_probe(tmp_path))
        assert r["passed"] is False
        assert "data/*.json" in r["issues"]

    def test_customized_and_wired_passes(self, tmp_path):
        proj = _copy_seed(tmp_path)
        # Make a real customization so the seed-identical check passes.
        ents = proj / "data" / "entities.json"
        body = json.loads(ents.read_text())
        # Rename a grunt to something canonical to simulate wave edit
        if "archetypes" in body and "grunt_melee" in body["archetypes"]:
            body["archetypes"]["Octorok"] = body["archetypes"].pop("grunt_melee")
        ents.write_text(json.dumps(body))
        r = asyncio.run(gamedev_scaffold_probe(proj))
        assert r["passed"] is True, f"expected pass, got {r}"
        assert "gamedev-scaffold" in r["raw"]

    def test_parse_error_in_data_file(self, tmp_path):
        proj = _copy_seed(tmp_path)
        (proj / "data" / "entities.json").write_text("{not json")
        r = asyncio.run(gamedev_scaffold_probe(proj))
        assert r["passed"] is False
        assert "parse error" in r["issues"].lower()


# ---------------------------------------------------------------------------
# dispatch routing
# ---------------------------------------------------------------------------

class TestDispatchRouting:
    def test_routes_to_scaffold_probe_when_data_dir_present(self, tmp_path):
        # Seed has both package.json + data/*.json → scaffold probe wins
        proj = _copy_seed(tmp_path)
        r = asyncio.run(gamedev_probe_dispatch(proj))
        # Scaffold probe's raw string is distinctive
        assert "gamedev-scaffold" in r["raw"]

    def test_routes_to_legacy_probe_when_only_game_definition(self, tmp_path):
        # No package.json, no data/ — but has public/game_definition.json
        (tmp_path / "public").mkdir()
        (tmp_path / "public" / "game_definition.json").write_text(json.dumps({
            "scenes": {"main": {"entities": []}},
            "mechanics": [],
            "entities": [],
        }))
        r = asyncio.run(gamedev_probe_dispatch(tmp_path))
        # Legacy probe's raw says "game_definition.json:"
        assert "game_definition.json:" in r["raw"]

    def test_missing_project_returns_skip(self, tmp_path):
        r = asyncio.run(gamedev_probe_dispatch(tmp_path / "does-not-exist"))
        assert r.get("passed") is True  # skip is non-blocking
        assert "skip" in (r.get("issues", "") or r.get("raw", "")).lower() \
            or r.get("raw", "").startswith("skip:") \
            or "no project" in r.get("raw", "").lower()
