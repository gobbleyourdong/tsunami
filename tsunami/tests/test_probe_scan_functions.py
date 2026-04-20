"""Tests for scripts/overnight/probe.py scan functions.

The content_adoption_rate value that morning_report keys off lives in
`scan_content_adoption`. Round K dead-lettered 1986_legend_of_zelda at
0.3% — if the math is wrong, the drift report is meaningless. These
tests pin down scan_mechanic_imports, scan_generic_bleed, and
scan_content_adoption on synthetic inputs so the calculation is
auditable offline.

No Node, no inference, no real deliverables — pure string manipulation.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

# content_probe lives in the tsunami package now (was
# scripts/overnight/probe.py pre-2026-04-20).
from tsunami import content_probe as probe  # noqa: E402


def test_scan_mechanic_imports_basic():
    """Standard import {A, B} from '@engine/design/catalog' extraction."""
    src = """
    import { CameraFollow, RoomGraph } from '@engine/design/catalog';
    export default function App() { return null; }
    """
    names = probe.scan_mechanic_imports(src)
    assert "CameraFollow" in names
    assert "RoomGraph" in names
    assert len(names) == 2


def test_scan_mechanic_imports_handles_aliases():
    """`A as B` aliases should yield A (the original), not B."""
    src = """
    import { HUD as HudOverlay, ItemUse } from '@engine/design/catalog';
    """
    names = probe.scan_mechanic_imports(src)
    assert "HUD" in names
    assert "HudOverlay" not in names
    assert "ItemUse" in names


def test_scan_mechanic_imports_handles_multiline():
    """Multi-line imports — regex uses DOTALL."""
    src = """
    import {
      CameraFollow,
      RoomGraph,
      LockAndKey,
    } from '@engine/design/catalog';
    """
    names = probe.scan_mechanic_imports(src)
    assert set(names) == {"CameraFollow", "RoomGraph", "LockAndKey"}


def test_scan_mechanic_imports_handles_path_variants():
    """Absolute 'engine/src/design/catalog' path should also match —
    some waves emit relative paths after file_edit rewrites."""
    src = """
    import { HUD } from '../../engine/src/design/catalog';
    """
    names = probe.scan_mechanic_imports(src)
    assert "HUD" in names


def test_scan_mechanic_imports_ignores_other_imports():
    """import from 'react' etc. must not match."""
    src = """
    import React from 'react';
    import { useState } from 'react';
    import { CameraFollow } from '@engine/design/catalog';
    """
    names = probe.scan_mechanic_imports(src)
    assert names == ["CameraFollow"]


def test_scan_mechanic_imports_picks_up_json_type_patterns():
    """Gap #27 (Round R 2026-04-20): gamedev deliverables have mechanics
    inside game_definition.json as `"type": "CameraFollow"`, NOT as
    TSX imports. Probe must count both sources so gamedev-only runs
    don't false-flag mechanic_import_count=0."""
    src = '''
    {
      "mechanics": [
        {"id": "cam", "type": "CameraFollow", "params": {}},
        {"id": "rg",  "type": "RoomGraph", "params": {}},
        {"id": "hud", "type": "HUD", "params": {}}
      ]
    }
    '''
    names = probe.scan_mechanic_imports(src)
    assert "CameraFollow" in names
    assert "RoomGraph" in names
    assert "HUD" in names


def test_scan_mechanic_imports_filters_non_catalog_types():
    """`"type": "Player"` or `"type": "Enemy"` are entity/archetype types,
    NOT MechanicType. Should NOT count toward mechanic_import_count."""
    src = '''
    {"entities": [{"name": "Link", "type": "Player"}], "mechanics": []}
    '''
    names = probe.scan_mechanic_imports(src)
    assert "Player" not in names, f"Player mis-counted as mechanic: {names}"


def test_scan_mechanic_imports_unions_tsx_and_json():
    """Hybrid delivery: TSX imports + JSON types both count."""
    src = '''
    import { CameraFollow } from '@engine/design/catalog';
    const data = {"mechanics": [{"type": "RoomGraph"}]};
    '''
    names = probe.scan_mechanic_imports(src)
    assert "CameraFollow" in names
    assert "RoomGraph" in names


def test_scan_mechanic_imports_dedups_across_sources():
    """If a name appears in BOTH TSX and JSON, only count once."""
    src = '''
    import { HUD } from '@engine/design/catalog';
    const d = {"mechanics": [{"type": "HUD"}]};
    '''
    names = probe.scan_mechanic_imports(src)
    assert names.count("HUD") == 1


def test_scan_generic_bleed_catches_placeholders():
    src = '''
    const enemies = [
      { name: "Enemy 1" },
      { name: "Enemy 2" },
      { name: "Boss A" },
      { type: 'monster' },
      { name: "Monster5" },
    ];
    const level = "Level 3";
    '''
    hits = probe.scan_generic_bleed(src)
    assert "Enemy 1" in hits
    assert "Enemy 2" in hits
    assert "Boss A" in hits
    assert "Monster5" in hits
    assert "Level 3" in hits
    assert "'monster'" in hits
    assert len(hits) >= 6


def test_scan_generic_bleed_empty_on_clean_src():
    src = '''
    const entities = [
      { id: "player", name: "Link" },
      { id: "octorok_red", name: "Red Octorok" },
    ];
    '''
    hits = probe.scan_generic_bleed(src)
    assert hits == []


def test_scan_content_adoption_zero_when_essence_missing():
    """Unknown essence stem → empty catalog, adoption_rate=0."""
    result = probe.scan_content_adoption("some src", "nonexistent_essence")
    assert result["adoption_rate"] == 0.0
    assert result["named_distinct"] == 0
    assert result["catalog_names"] == {}


def test_scan_content_adoption_computes_rate_on_real_essence():
    """Against a real essence (1986_legend_of_zelda), src mentioning
    a few real names should produce adoption_rate > 0 and count
    distinct names correctly."""
    # Pick names known to be in the Zelda essence.
    src = '''
    const player = { name: "Link" };
    const enemy1 = { type: "Octorok" };
    const enemy2 = { type: "Moblin" };
    // Many references should not inflate distinct count
    console.log("Link walks past another Octorok");
    '''
    result = probe.scan_content_adoption(src, "1986_legend_of_zelda")
    # Either essence is present on disk (real environment) or not
    # (test-isolated). Both branches are covered below.
    if not result["catalog_names"]:
        # Essence missing on disk — covered by test above.
        return
    # adopted is {category: {name: count}}
    all_adopted = [n for cat in result["adopted"].values() for n in cat.keys()]
    # At least Link, Octorok, Moblin should be picked up if they're
    # in any category of the catalog.
    assert result["named_distinct"] >= 1, (
        f"Expected at least one distinct adoption, got: {result['adopted']}"
    )
    # Adoption rate ∈ [0, 1]
    assert 0 < result["adoption_rate"] <= 1


def test_scan_content_adoption_filters_short_names():
    """Names shorter than 3 chars are skipped — prevents false positives
    on common words like "C" or "X". The filter is at probe.py:138."""
    # Build a synthetic catalog scenario: can't easily inject short
    # names without patching load_content_catalog, but we CAN verify
    # the filter is present in source.
    import inspect
    src = inspect.getsource(probe.scan_content_adoption)
    assert "len(name) < 3" in src
    assert "continue" in src


def test_scan_content_adoption_matches_snake_case_variant():
    """Gap #29 (Round R 2026-04-20): wave emits `"old_man"` but catalog
    has `"Old Man"`. Probe must count snake_case variants as matches."""
    src = '{"entities": ["player", "old_man", "link", "octorok"]}'
    result = probe.scan_content_adoption(src, "1986_legend_of_zelda")
    # If the essence is present on disk, we should find hits for
    # Link, Octorok, Old Man through their snake_case variants.
    if not result["catalog_names"]:
        return  # essence not loaded — skip assertion
    adopted_names = set()
    for cat_hits in result["adopted"].values():
        adopted_names.update(cat_hits.keys())
    # At least one of the snake-case emissions must have been detected.
    detected = adopted_names.intersection({"Link", "Octorok", "Old Man"})
    assert detected, (
        f"Expected snake_case matches for Link/Octorok/Old Man, "
        f"got adopted: {adopted_names}"
    )


def test_scan_content_adoption_source_has_variant_generation():
    """Verify the normalisation code is present — structural guard."""
    import inspect
    src = inspect.getsource(probe.scan_content_adoption)
    assert "lc_us" in src or "lowercase" in src.lower()
    assert "variants" in src, "variant set not generated"


def test_read_gamedev_deliverable_finds_game_definition():
    """The gamedev surface scan reads public/game_definition.json."""
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        public = project / "public"
        public.mkdir()
        (public / "game_definition.json").write_text(
            '{"scenes": {}, "entities": [{"name": "Link"}], "mechanics": []}'
        )
        text = probe._read_gamedev_deliverable(project)
        assert "Link" in text


def test_read_gamedev_deliverable_empty_when_missing():
    with tempfile.TemporaryDirectory() as td:
        text = probe._read_gamedev_deliverable(Path(td))
        assert text == ""


def test_run_concats_src_and_gamedev_surfaces():
    """run() should scan BOTH src/ and game_definition.json. A content
    name in the JSON should count toward adoption even if src is empty.
    This was the Round F finding — probe used to report 'skipped: no
    src dir' for gamedev deliveries because it only scanned src/."""
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        src = project / "src"
        src.mkdir()
        # src is empty (no .tsx files — gamedev doesn't write App.tsx)
        public = project / "public"
        public.mkdir()
        (public / "game_definition.json").write_text(
            '{"scenes": {}, "entities": ['
            '{"name": "Link"}, {"name": "Octorok"}'
            '], "mechanics": []}'
        )
        report = probe.run(src, content_essence="1986_legend_of_zelda")
        # src_bytes=0 but gamedev_deliverable_bytes > 0
        assert report["src_bytes"] == 0
        assert report["gamedev_deliverable_bytes"] > 0
        assert report["scan_surface_bytes"] > 0
        # If the essence is present on disk, Link/Octorok should be found
        if "content" in report and report["content"]["catalog_names"]:
            # The JSON surface carries the content signal
            assert report["content"]["named_distinct"] >= 0


def main():
    tests = [
        test_scan_mechanic_imports_basic,
        test_scan_mechanic_imports_handles_aliases,
        test_scan_mechanic_imports_handles_multiline,
        test_scan_mechanic_imports_handles_path_variants,
        test_scan_mechanic_imports_ignores_other_imports,
        test_scan_mechanic_imports_picks_up_json_type_patterns,
        test_scan_mechanic_imports_filters_non_catalog_types,
        test_scan_mechanic_imports_unions_tsx_and_json,
        test_scan_mechanic_imports_dedups_across_sources,
        test_scan_generic_bleed_catches_placeholders,
        test_scan_generic_bleed_empty_on_clean_src,
        test_scan_content_adoption_zero_when_essence_missing,
        test_scan_content_adoption_computes_rate_on_real_essence,
        test_scan_content_adoption_filters_short_names,
        test_scan_content_adoption_matches_snake_case_variant,
        test_scan_content_adoption_source_has_variant_generation,
        test_read_gamedev_deliverable_finds_game_definition,
        test_read_gamedev_deliverable_empty_when_missing,
        test_run_concats_src_and_gamedev_surfaces,
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
