"""Runtime tests for deliver_gates.code_write_gate scaffold routing.

Gap #22 (Round N 2026-04-20) was caught because the _flags dict at
agent.py:4673 didn't pass 'target_scaffold' to run_deliver_gates.
code_write_gate's gamedev branch (deliver_gates.py:101) only fires
when `state_flags.get("target_scaffold") == "gamedev"`.

These tests invoke code_write_gate directly with synthetic state_flags
to prove the routing works as intended. Complements the static text-
check tests in test_gamedev_delivery_gate_opened.py and
test_scaffold_aware_nudges.py.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.deliver_gates import code_write_gate


def test_gamedev_passes_when_game_definition_json_exists():
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        public = project / "public"
        public.mkdir()
        (public / "game_definition.json").write_text('{"scenes": [], "mechanics": []}')
        flags = {"target_scaffold": "gamedev"}
        result = code_write_gate(flags, project)
        assert result.passed is True, f"should pass: {result.message}"
        assert "game_definition.json" in result.message


def test_gamedev_fails_without_game_definition_json():
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        flags = {"target_scaffold": "gamedev"}
        result = code_write_gate(flags, project)
        assert result.passed is False
        assert "game_definition.json" in result.message
        # Gamedev-specific system_note — wave should be told about emit_design
        assert "emit_design" in result.system_note
        # App.tsx may appear, but only in a negation context ("Do NOT write").
        # The key test: the gamedev note must NOT tell the wave to "write App.tsx"
        # as the fix (the React advisory). Look for that specific pattern.
        lower = result.system_note.lower()
        assert "do not write" in lower and "app.tsx" in lower, (
            "gamedev bounce must explicitly forbid App.tsx, not suggest it. "
            f"Got: {result.system_note!r}"
        )


def test_gamedev_accepts_root_game_definition_fallback():
    """Some emit_design outputs land at project root, not public/."""
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        (project / "game_definition.json").write_text('{}')
        flags = {"target_scaffold": "gamedev"}
        result = code_write_gate(flags, project)
        assert result.passed is True


def test_react_branch_on_empty_scaffold():
    """When target_scaffold is missing/empty, falls through to React
    logic — checks app_source_written flag."""
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        flags = {"target_scaffold": "", "app_source_written": False}
        result = code_write_gate(flags, project)
        assert result.passed is False
        assert "App.tsx" in result.message


def test_react_branch_accepts_dist_index_html():
    """React-path fallback: dist/index.html exists, delivery passes
    even if app_source_written wasn't set."""
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        dist = project / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>")
        flags = {"target_scaffold": "react-app", "app_source_written": False}
        result = code_write_gate(flags, project)
        assert result.passed is True
        assert "dist/index.html" in result.message


def test_react_branch_passes_on_app_source_written():
    flags = {"target_scaffold": "react-app", "app_source_written": True}
    with tempfile.TemporaryDirectory() as td:
        result = code_write_gate(flags, Path(td))
        assert result.passed is True


def test_scaffold_routing_is_case_sensitive():
    """`target_scaffold == "gamedev"` is case-sensitive. Misspelled
    or capitalized variants route to React (not ideal, but documented
    behavior — keeps the check tight rather than fuzzy-matching)."""
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        # `GameDev` with weird case routes to React branch
        flags = {"target_scaffold": "GameDev", "app_source_written": False}
        result = code_write_gate(flags, project)
        # No game_definition.json, no app_source_written, no dist/ →
        # React branch fires with App.tsx message
        assert result.passed is False
        assert "App.tsx" in result.message


def test_run_deliver_gates_returns_first_failure():
    """run_deliver_gates should return the first gate failure and
    short-circuit — don't run subsequent gates if one already failed."""
    from tsunami.deliver_gates import run_deliver_gates
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        # Empty gamedev project — code_write_gate should fail first.
        flags = {"target_scaffold": "gamedev"}
        result = run_deliver_gates(flags, project, max_attempts=2, attempt_number=1)
        assert result is not None
        assert result.gate == "code_write"
        assert "game_definition.json" in result.log_message


def test_run_deliver_gates_budget_exhausted_passes_soft_fails():
    """When attempt_number > max_attempts, soft gate failures pass
    through silently — but hard gates (like asset_existence) still fire."""
    from tsunami.deliver_gates import run_deliver_gates
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        # Gamedev with no game_definition.json = soft-fail code_write.
        # Budget exhausted → soft fail skipped → returns None (passes).
        flags = {"target_scaffold": "gamedev"}
        result = run_deliver_gates(flags, project, max_attempts=2, attempt_number=3)
        assert result is None, (
            f"budget-exhausted soft gates should pass, got {result}"
        )


def test_run_deliver_gates_passes_valid_gamedev_delivery():
    """Full pass-through: gamedev with game_definition.json + no
    missing assets = all gates return passed, run_deliver_gates returns None."""
    from tsunami.deliver_gates import run_deliver_gates
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        public = project / "public"
        public.mkdir()
        (public / "game_definition.json").write_text('{}')
        # No src/ dir, so asset_existence returns passed (no src/ to scan).
        flags = {"target_scaffold": "gamedev"}
        result = run_deliver_gates(flags, project, max_attempts=2, attempt_number=1)
        assert result is None, f"valid delivery should pass, got {result}"


def test_run_deliver_gates_none_project_dir_doesnt_crash():
    """If project_dir is None (no deliverables yet), gates should
    handle gracefully — don't crash, return failure or None."""
    from tsunami.deliver_gates import run_deliver_gates
    flags = {"target_scaffold": "gamedev"}
    # Should not raise
    try:
        result = run_deliver_gates(flags, None, max_attempts=2, attempt_number=1)
    except Exception as e:
        raise AssertionError(f"run_deliver_gates crashed on None project_dir: {e}")
    # Result may be failure or None, but must not be an exception.
    assert result is None or hasattr(result, 'gate')


def main():
    tests = [
        test_gamedev_passes_when_game_definition_json_exists,
        test_gamedev_fails_without_game_definition_json,
        test_gamedev_accepts_root_game_definition_fallback,
        test_react_branch_on_empty_scaffold,
        test_react_branch_accepts_dist_index_html,
        test_react_branch_passes_on_app_source_written,
        test_scaffold_routing_is_case_sensitive,
        test_run_deliver_gates_returns_first_failure,
        test_run_deliver_gates_budget_exhausted_passes_soft_fails,
        test_run_deliver_gates_passes_valid_gamedev_delivery,
        test_run_deliver_gates_none_project_dir_doesnt_crash,
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
