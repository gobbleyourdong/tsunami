"""Tests for PhaseMachine phase-transition methods.

Phase machine tracks the agent's progression through SCAFFOLD → WRITE
→ BUILD → TEST → DELIVER. A bug in _advance/_retreat/skip_scaffold
would cause phase drift (e.g. stuck in SCAFFOLD after a successful
file_write) which silently mis-routes downstream gates and nudges.

These tests pin the invariants: _advance never moves backward,
_retreat never moves forward, skip_scaffold jumps to WRITE and
records project_path, record() tracks counters correctly.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.phase_machine import PhaseMachine, Phase  # noqa: E402


def test_initial_phase_is_scaffold():
    pm = PhaseMachine()
    assert pm.phase == Phase.SCAFFOLD
    assert pm.iters_in_phase == 0
    assert pm.files_written == 0


def test_advance_moves_forward():
    pm = PhaseMachine()
    pm._advance(Phase.WRITE)
    assert pm.phase == Phase.WRITE
    # iter counter resets on advance
    assert pm.iters_in_phase == 0


def test_advance_never_moves_backward():
    """_advance must ONLY move forward. Calling with a lower phase
    should be a no-op — otherwise a late SCAFFOLD signal could undo
    a successful advance to WRITE."""
    pm = PhaseMachine()
    pm._advance(Phase.DELIVER)
    assert pm.phase == Phase.DELIVER
    pm._advance(Phase.SCAFFOLD)  # should not go back
    assert pm.phase == Phase.DELIVER, "phase moved backward on _advance"


def test_retreat_moves_backward():
    pm = PhaseMachine()
    pm._advance(Phase.BUILD)
    pm._retreat(Phase.WRITE, "build failed")
    assert pm.phase == Phase.WRITE
    assert pm.iters_in_phase == 0


def test_retreat_never_moves_forward():
    """_retreat must ONLY move backward."""
    pm = PhaseMachine()
    pm._advance(Phase.WRITE)
    pm._retreat(Phase.DELIVER, "bogus")  # should not advance via retreat
    assert pm.phase == Phase.WRITE, "phase moved forward on _retreat"


def test_skip_scaffold_jumps_to_write():
    pm = PhaseMachine()
    pm.skip_scaffold("/tmp/somewhere")
    assert pm.phase == Phase.WRITE
    assert pm.project_path == "/tmp/somewhere"


def test_skip_scaffold_without_path():
    pm = PhaseMachine()
    pm.skip_scaffold()
    assert pm.phase == Phase.WRITE
    assert pm.project_path is None


def test_record_advances_on_project_init():
    pm = PhaseMachine()
    pm.record("project_init", {"name": "foo"}, result_content="ok", is_error=False)
    assert pm.phase == Phase.WRITE
    assert pm.project_path == "workspace/deliverables/foo"


def test_record_counts_file_writes():
    pm = PhaseMachine()
    pm.record("file_write", {"path": "x"}, result_content="ok", is_error=False)
    pm.record("file_edit", {"path": "y"}, result_content="ok", is_error=False)
    assert pm.files_written == 2


def test_record_advances_to_test_on_build_success():
    pm = PhaseMachine()
    pm._advance(Phase.BUILD)
    # vite-style success marker
    pm.record("shell_exec", {"command": "npx vite build"},
              result_content="vite v5 built in 3.4s", is_error=False)
    assert pm.phase == Phase.TEST
    assert pm.build_passed is True


def test_record_retreats_on_build_failure():
    pm = PhaseMachine()
    pm._advance(Phase.BUILD)
    pm.record("shell_exec", {"command": "npx vite build"},
              result_content="error TS2339", is_error=True)
    # Build failure retreats to WRITE
    assert pm.phase == Phase.WRITE


def test_record_retreats_on_undertow_failure():
    pm = PhaseMachine()
    pm._advance(Phase.TEST)
    pm.record("undertow", {}, result_content="issues: broken layout", is_error=True)
    assert pm.phase == Phase.WRITE


def test_status_returns_consistent_keys():
    pm = PhaseMachine()
    pm._advance(Phase.WRITE)
    s = pm.status()
    for key in ("phase", "iters_in_phase", "total_iters", "files_written",
                "build_passed", "test_passed", "project_path"):
        assert key in s, f"status missing {key}"
    assert s["phase"] == "WRITE"


def test_iters_in_phase_resets_on_advance():
    pm = PhaseMachine()
    # Simulate 3 iterations in SCAFFOLD
    for _ in range(3):
        pm.record("file_read", {"path": "x"}, result_content="", is_error=False)
    assert pm.iters_in_phase == 3
    # Advance to WRITE
    pm.record("project_init", {"name": "foo"}, result_content="ok", is_error=False)
    # After record: iters_in_phase incremented to 4, then _advance resets to 0
    assert pm.iters_in_phase == 0


def main():
    tests = [
        test_initial_phase_is_scaffold,
        test_advance_moves_forward,
        test_advance_never_moves_backward,
        test_retreat_moves_backward,
        test_retreat_never_moves_forward,
        test_skip_scaffold_jumps_to_write,
        test_skip_scaffold_without_path,
        test_record_advances_on_project_init,
        test_record_counts_file_writes,
        test_record_advances_to_test_on_build_success,
        test_record_retreats_on_build_failure,
        test_record_retreats_on_undertow_failure,
        test_status_returns_consistent_keys,
        test_iters_in_phase_resets_on_advance,
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
