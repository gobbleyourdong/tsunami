"""Tests for the scaffold-customization path in tsunami.content_probe.

Guards the new metric (scan_scaffold_customization) + the extension
of _read_gamedev_deliverable to cover data/*.json + src/scenes/*.ts
without breaking the legacy game_definition.json behavior that the
existing test_probe_scan_functions suite already covers.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tsunami.content_probe import (
    _bucket_for_ratio,
    _detect_scaffold_kind,
    _read_gamedev_deliverable,
    run as probe_run,
    scan_scaffold_customization,
)


REPO = Path(__file__).resolve().parent.parent.parent
SEED_ACTION = REPO / "scaffolds" / "gamedev" / "action_adventure"


def _copy_scaffold(seed: Path, dst: Path) -> Path:
    """Copy a scaffold seed into dst and return the copy path."""
    shutil.copytree(seed, dst)
    return dst


# ---------------------------------------------------------------------------
# bucket mapping
# ---------------------------------------------------------------------------

class TestCustomizationBucket:
    def test_zero_is_untouched(self):
        assert _bucket_for_ratio(0.0) == "untouched"

    def test_small_is_surface(self):
        assert _bucket_for_ratio(0.10) == "surface_edit"

    def test_mid_is_substantive(self):
        assert _bucket_for_ratio(0.35) == "substantive"

    def test_high_is_heavy_rewrite(self):
        assert _bucket_for_ratio(0.70) == "heavy_rewrite"

    def test_edge_below_surface(self):
        # 0.15 is the surface / substantive boundary — <0.15 → surface
        assert _bucket_for_ratio(0.149) == "surface_edit"
        assert _bucket_for_ratio(0.15) == "substantive"


# ---------------------------------------------------------------------------
# scaffold-kind detection
# ---------------------------------------------------------------------------

class TestDetectScaffoldKind:
    def test_pristine_action_adventure(self):
        assert _detect_scaffold_kind(SEED_ACTION) == "action_adventure"

    def test_missing_package_json(self, tmp_path):
        assert _detect_scaffold_kind(tmp_path) is None

    def test_non_scaffold_package_name(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "something-else"}))
        assert _detect_scaffold_kind(tmp_path) is None

    def test_scaffold_name_but_unknown_kind(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "gamedev-not-a-real-kind-scaffold"})
        )
        assert _detect_scaffold_kind(tmp_path) is None


# ---------------------------------------------------------------------------
# customization scanner
# ---------------------------------------------------------------------------

class TestScaffoldCustomization:
    def test_pristine_seed_reports_untouched(self):
        r = scan_scaffold_customization(SEED_ACTION)
        assert r["applicable"] is True
        assert r["seed_kind"] == "action_adventure"
        assert r["data_files_modified"] == 0
        assert r["customization_ratio"] == 0.0
        assert r["customization_bucket"] == "untouched"
        assert r["scenes_modified"] is False

    def test_unknown_kind_returns_not_applicable(self, tmp_path):
        r = scan_scaffold_customization(tmp_path)
        assert r["applicable"] is False
        assert r["seed_kind"] is None
        assert r["customization_bucket"] == "untouched"

    def test_one_modified_data_file(self, tmp_path):
        # Copy the seed, then bump one data file.
        proj = _copy_scaffold(SEED_ACTION, tmp_path / "proj")
        ents = proj / "data" / "entities.json"
        ents.write_text(ents.read_text() + "\n// bumped")  # invalid JSON but content differs
        r = scan_scaffold_customization(proj)
        assert r["data_files_modified"] == 1
        assert "entities.json" in r["modified_files"]
        # 1 of 5 files → ratio ~0.2 → substantive bucket
        assert r["customization_bucket"] == "substantive"

    def test_wave_added_new_data_file(self, tmp_path):
        proj = _copy_scaffold(SEED_ACTION, tmp_path / "proj")
        (proj / "data" / "custom_bosses.json").write_text('{"bosses":[]}')
        r = scan_scaffold_customization(proj)
        assert "custom_bosses.json" in r["modified_files"]
        assert r["data_files_modified"] >= 1

    def test_heavy_rewrite_flips_bucket(self, tmp_path):
        proj = _copy_scaffold(SEED_ACTION, tmp_path / "proj")
        # Bump every data file
        for f in (proj / "data").glob("*.json"):
            f.write_text(f.read_text() + "\n")
        r = scan_scaffold_customization(proj)
        assert r["customization_ratio"] == 1.0
        assert r["customization_bucket"] == "heavy_rewrite"


# ---------------------------------------------------------------------------
# deliverable surface: data/*.json + scenes
# ---------------------------------------------------------------------------

class TestReadGamedevDeliverable:
    def test_includes_all_data_jsons(self):
        blob = _read_gamedev_deliverable(SEED_ACTION)
        # Every data file name should appear at least as part of its
        # payload content (archetypes/rooms/items/mechanics/config)
        for token in ("archetypes", "rooms", "items", "mechanics"):
            assert token in blob, f"expected '{token}' in deliverable blob"

    def test_includes_scene_ts(self):
        blob = _read_gamedev_deliverable(SEED_ACTION)
        # Scenes import from @engine — that import line should show up
        assert "@engine" in blob or "engine" in blob

    def test_empty_project_returns_empty_blob(self, tmp_path):
        assert _read_gamedev_deliverable(tmp_path) == ""


# ---------------------------------------------------------------------------
# end-to-end run()
# ---------------------------------------------------------------------------

class TestRunPipelineIncludesCustomization:
    def test_pristine_seed_run_includes_customization_block(self):
        report = probe_run(SEED_ACTION)
        assert "customization" in report
        c = report["customization"]
        assert c["applicable"] is True
        assert c["customization_bucket"] == "untouched"
        # The scan surface should still include data/*.json bytes
        assert report["gamedev_deliverable_bytes"] > 0

    def test_run_on_src_dir_resolves_to_project_root(self, tmp_path):
        proj = _copy_scaffold(SEED_ACTION, tmp_path / "proj")
        src = proj / "src"
        assert src.is_dir()
        report = probe_run(src)
        # project_dir should be the parent of src → proj
        assert Path(report["project_dir"]) == proj
        assert report["customization"]["seed_kind"] == "action_adventure"
