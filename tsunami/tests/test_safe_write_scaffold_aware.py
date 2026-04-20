"""Tests for the scaffold-aware workspace-root-write error message (Fix #10).

Round D on /tmp/live_zelda_round2 captured the wave trying to
file_write game_design.json to workspace root. Safe-write correctly
blocked it, but the remediation hint said "Call project_init" —
which is the REACT-scaffold tool, not the gamedev flow. The wave
shouldn't be told to project_init when its prompt is for a game.

Fix #10: the scaffold-aware hint now emits emit_design guidance for
game_*.json filenames. Other filenames get the default project_init
hint unchanged.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.tools.filesystem import _is_safe_write  # noqa: E402


def test_game_definition_json_routes_to_emit_design():
    with tempfile.TemporaryDirectory() as ws:
        target = Path(ws) / "game_definition.json"
        err = _is_safe_write(target, ws)
        assert err is not None
        assert "emit_design" in err
        assert "project_init" not in err  # the wrong hint is gone


def test_game_design_json_routes_to_emit_design():
    """The exact filename Round D used — 'game_design.json' (not the
    canonical 'game_definition.json', but we alias it)."""
    with tempfile.TemporaryDirectory() as ws:
        target = Path(ws) / "game_design.json"
        err = _is_safe_write(target, ws)
        assert err is not None, "should block root write"
        assert "emit_design" in err


def test_game_prefixed_json_routes_to_emit_design():
    with tempfile.TemporaryDirectory() as ws:
        target = Path(ws) / "game_variant_42.json"
        err = _is_safe_write(target, ws)
        assert "emit_design" in err


def test_non_game_json_keeps_project_init_hint():
    with tempfile.TemporaryDirectory() as ws:
        target = Path(ws) / "config.json"
        err = _is_safe_write(target, ws)
        assert err is not None
        assert "project_init" in err
        assert "emit_design" not in err


def test_app_tsx_keeps_project_init_hint():
    with tempfile.TemporaryDirectory() as ws:
        target = Path(ws) / "App.tsx"
        err = _is_safe_write(target, ws)
        assert err is not None
        assert "project_init" in err


def test_deep_path_not_blocked():
    with tempfile.TemporaryDirectory() as ws:
        # Writes INSIDE a project dir are fine
        proj = Path(ws) / "deliverables" / "zelda" / "public"
        proj.mkdir(parents=True)
        target = proj / "game_definition.json"
        err = _is_safe_write(target, ws)
        # May still return None or a different (non-workspace-root) error —
        # the important thing is that it's NOT the root-write-blocked message
        if err is not None:
            assert "land directly in workspace/ root" not in err


def main():
    tests = [
        test_game_definition_json_routes_to_emit_design,
        test_game_design_json_routes_to_emit_design,
        test_game_prefixed_json_routes_to_emit_design,
        test_non_game_json_keeps_project_init_hint,
        test_app_tsx_keeps_project_init_hint,
        test_deep_path_not_blocked,
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
