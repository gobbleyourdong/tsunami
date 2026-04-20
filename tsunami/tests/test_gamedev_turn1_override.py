"""Tests for the turn-1 gamedev system-prompt override (Fix #12).

Round E on /tmp/live_zelda_round5 captured the wave going down the
React-build path even with gamedev scaffold + genre + content
directives all active — because build_system_prompt runs BEFORE
pick_scaffold + plan_manager.from_scaffold, so turn 1 used the
React-biased lite prompt.

Fix #12: after building the system prompt, peek pick_scaffold on
user_message. If it returns 'gamedev', append a turn-1 override
block steering the wave to emit_design / file_read schema.ts
instead of project_init / file_write App.tsx.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))


def test_agent_py_has_gamedev_turn1_override():
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    assert "GAMEDEV OVERRIDE (turn-1)" in agent_py, (
        "turn-1 override block missing — React-bias regression will recur"
    )
    # The override should specifically reference the canonical gamedev
    # first moves: read schema.ts, emit_design.
    assert "schema.ts" in agent_py
    assert "emit_design" in agent_py
    assert "NOT file_write" in agent_py


def test_override_is_conditional_on_gamedev():
    """The override must ONLY append for gamedev scaffolds, not
    react-build / dashboard / landing."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # The conditional block must exist
    assert 'if _peek_scaffold == "gamedev":' in agent_py


def test_override_peeks_pick_scaffold():
    """The override derives scaffold_kind from pick_scaffold, not from
    plan_manager (which isn't populated yet at this point in run())."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # Find the override block, verify pick_scaffold is called nearby.
    # Window widened 2026-04-20 after absolute-path derivation added
    # ~500 chars between the pick_scaffold call and the override text.
    idx = agent_py.find("GAMEDEV OVERRIDE (turn-1)")
    window = agent_py[max(0, idx - 1500):idx + 1500]
    assert "pick_scaffold" in window
    assert "_peek_scaffold" in window


def test_override_survives_pick_failure():
    """If pick_scaffold raises, the override block must swallow the
    exception and NOT crash system-prompt assembly. This is a try/except
    correctness check via code inspection."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    idx = agent_py.find("GAMEDEV OVERRIDE (turn-1)")
    # Window widened 2026-04-20 after override body grew with common-
    # failure documentation (~1.5KB added). try/except landed further
    # AFTER the marker than before.
    window = agent_py[max(0, idx - 2000):idx + 4000]
    # The surrounding try/except must cover the override assembly
    assert "except Exception" in window
    assert "Gamedev turn-1 override skipped" in window


def test_override_uses_absolute_paths():
    """Round F 2026-04-20 captured: the wave obeyed the override and
    called `file_read scaffolds/engine/src/design/schema.ts` — but
    file_read resolved that relative to the worker's workspace. The
    fix: derive absolute paths from agent.py's own location and inject
    them into the override string."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    idx = agent_py.find("GAMEDEV OVERRIDE (turn-1)")
    window = agent_py[idx - 1500:idx + 2000]
    # The fix computes a repo root from this file's location
    assert "Path(__file__).resolve().parent.parent" in window, (
        "override must derive absolute paths from agent.py's location"
    )
    assert "_engine_schema" in window
    assert "_engine_catalog" in window
    # The format-string must interpolate those paths (f-string with {_engine_schema})
    assert "{_engine_schema}" in window
    assert "{_engine_catalog}" in window


def test_override_absolute_paths_actually_resolve():
    """Compute the same paths the override uses at import-time and
    verify they point at real files. If schema.ts moves, this test
    catches it before a live run wastes 25 min of inference."""
    import tsunami.agent as _a
    repo_root = Path(_a.__file__).resolve().parent.parent
    schema_path = repo_root / "scaffolds" / "engine" / "src" / "design" / "schema.ts"
    catalog_path = repo_root / "scaffolds" / "engine" / "src" / "design" / "catalog.ts"
    assert schema_path.is_file(), f"schema.ts missing at {schema_path}"
    assert catalog_path.is_file(), f"catalog.ts missing at {catalog_path}"
    # Sanity: schema contains MechanicType union
    assert "MechanicType" in schema_path.read_text()


def main():
    tests = [
        test_agent_py_has_gamedev_turn1_override,
        test_override_is_conditional_on_gamedev,
        test_override_peeks_pick_scaffold,
        test_override_survives_pick_failure,
        test_override_uses_absolute_paths,
        test_override_absolute_paths_actually_resolve,
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
