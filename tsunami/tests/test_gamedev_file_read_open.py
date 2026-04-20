"""Tests for gamedev file_read tool-availability (F-A4 / Fix #13).

Round D captured the wave being told: "Tool 'file_read' is not available
in this phase. Available: ['emit_design', 'file_edit', 'file_write',
'message_result']" — directly after plan_scaffolds/gamedev.md told it
to file_read schema.ts at Step 0.

Fix #13 (F-A4): when the active plan has a Design section (gamedev
signature), open file_read from turn 1, not waiting for
_first_write_done.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))


def test_agent_py_has_gamedev_file_read_opener():
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    assert "GAMEDEV-SPECIFIC file_read opening" in agent_py, (
        "F-A4 file_read opener missing — Round D-style failure will recur"
    )
    assert "plan_manager.section(\"Design\")" in agent_py, (
        "Design section check is the gamedev signature used to open file_read"
    )


def test_agent_py_still_has_generic_anti_spiral_gate():
    """The web-build anti-spiral gate (wait for _first_write_done before
    opening file_read) must still be there for NON-gamedev phases."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # The _first_write_done branch should remain
    assert "if self._first_write_done:" in agent_py
    # And the generic restore loop should still iterate file_read + shell_exec
    assert 'for _restore in ("file_read", "shell_exec"):' in agent_py


def test_file_read_open_comes_before_force_tool_path():
    """The force_tool branch (explicit narrow schema) must not be
    affected by the gamedev opener. Structural: the gamedev block sits
    inside the else of the `if force_tool:` branch."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    force_idx = agent_py.find("if force_tool:")
    gamedev_idx = agent_py.find("GAMEDEV-SPECIFIC file_read opening")
    assert force_idx > 0 and gamedev_idx > 0
    # gamedev block must come AFTER force_tool branch starts, AND must
    # be inside the else (bracketed by `else:` before `force_tool:` end)
    else_idx = agent_py.find("else:", force_idx)
    assert force_idx < else_idx < gamedev_idx, (
        "gamedev opener must live in the else branch of force_tool check"
    )


def main():
    tests = [
        test_agent_py_has_gamedev_file_read_opener,
        test_agent_py_still_has_generic_anti_spiral_gate,
        test_file_read_open_comes_before_force_tool_path,
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
