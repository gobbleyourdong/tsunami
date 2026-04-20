"""Tests for Fix #33: progress.detect_progress_signals scaffold-aware messaging.

Round T (2026-04-20) session log showed:
  Progress signal: no_code_writes — Pressure building. 10 iterations,
  zero writes. Write App.tsx NOW.

...fired on a gamedev run where the deliverable is
public/game_definition.json (emitted via emit_design), not App.tsx.
The wave correctly ignored the React-biased advisory, but the
advisory itself is wrong for gamedev.

Fix #33: `detect_progress_signals` now accepts `scaffold_kind` kwarg.
For gamedev, the no_code_writes nudge advises emit_design instead.
React-app behavior unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami.progress import detect_progress_signals  # noqa: E402


def _base_history():
    # 10 file_reads with no file_write — should trip no_code_writes at iter 10
    return ["file_read"] * 10


def test_react_default_preserves_app_tsx_advisory():
    """Default scaffold_kind (react-app) keeps the old App.tsx message."""
    sigs = detect_progress_signals(iteration=10, tool_history=_base_history())
    nudges = [s for s in sigs if s.name == "no_code_writes"]
    assert len(nudges) == 1
    assert "App.tsx" in nudges[0].message


def test_gamedev_scaffold_advises_emit_design():
    """Fix #33 main case: gamedev scaffold routes to emit_design advice."""
    sigs = detect_progress_signals(
        iteration=10, tool_history=_base_history(),
        scaffold_kind="gamedev",
    )
    nudges = [s for s in sigs if s.name == "no_code_writes"]
    assert len(nudges) == 1
    msg = nudges[0].message
    assert "emit_design" in msg, f"gamedev message missing emit_design: {msg}"
    # Must explicitly warn against App.tsx
    assert "game_definition.json" in msg or "NOT" in msg


def test_gamedev_message_mentions_correct_deliverable():
    """Gamedev message should reference public/game_definition.json."""
    sigs = detect_progress_signals(
        iteration=10, tool_history=_base_history(),
        scaffold_kind="gamedev",
    )
    msg = sigs[0].message
    assert "game_definition.json" in msg


def test_signal_name_unchanged_across_scaffolds():
    """Signal name stays 'no_code_writes' — downstream dispatch doesn't branch on scaffold."""
    react_sigs = detect_progress_signals(iteration=10, tool_history=_base_history())
    gd_sigs = detect_progress_signals(
        iteration=10, tool_history=_base_history(), scaffold_kind="gamedev"
    )
    assert react_sigs[0].name == gd_sigs[0].name == "no_code_writes"


def test_no_signal_when_writes_present():
    """Still no signal if the drone has been writing — regardless of scaffold."""
    history = ["file_read", "file_read", "file_write", "file_read"] * 3
    react_sigs = detect_progress_signals(iteration=10, tool_history=history)
    gd_sigs = detect_progress_signals(
        iteration=10, tool_history=history, scaffold_kind="gamedev"
    )
    assert not [s for s in react_sigs if s.name == "no_code_writes"]
    assert not [s for s in gd_sigs if s.name == "no_code_writes"]


def test_emit_design_counts_as_a_write():
    """Gap #34 (Round T 2026-04-20): emit_design must count as a code
    write so a gamedev wave that successfully emit_design'd doesn't
    trip the "no_code_writes" false-positive."""
    history = ["file_read"] * 5 + ["emit_design"] + ["file_read"] * 4
    # 10 total iters, 1 emit_design in the middle
    sigs = detect_progress_signals(
        iteration=10, tool_history=history, scaffold_kind="gamedev"
    )
    assert not [s for s in sigs if s.name == "no_code_writes"], (
        "emit_design should count as a write; no_code_writes shouldn't fire"
    )


def test_emit_design_prevents_long_stall():
    """A successful emit_design in the recent window should also
    prevent `long_stall` exit — Fix #34 extends to the stall-window
    check, not just the iter-10 nudge."""
    history = ["file_read"] * 25 + ["emit_design"] + ["file_read"] * 10
    # iteration=36 is past stall_check_after (30) but stall_window=20
    # should see the emit_design at position 25 (within last 20).
    sigs = detect_progress_signals(
        iteration=36, tool_history=history, scaffold_kind="gamedev"
    )
    # emit_design was 10 iters ago, within the default stall_window=20
    assert not [s for s in sigs if s.name == "long_stall"], (
        f"emit_design in recent window should prevent long_stall, got: "
        f"{[s.name for s in sigs]}"
    )


def test_signal_fires_only_at_early_nudge_iter():
    """Fires at iteration == early_nudge_at (default 10), not before/after."""
    for it in (5, 9, 11, 15):
        sigs = detect_progress_signals(
            iteration=it, tool_history=_base_history(),
            scaffold_kind="gamedev",
        )
        assert not any(s.name == "no_code_writes" for s in sigs), (
            f"no_code_writes should only fire at iter=10, fired at {it}"
        )


def test_agent_passes_scaffold_kind_to_progress():
    """agent.py's detect_progress_signals call must pass scaffold_kind
    derived from self._target_scaffold or plan.Design section."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # Look for the caller block
    idx = agent_py.find("detect_progress_signals")
    assert idx >= 0, "agent.py doesn't call detect_progress_signals"
    # 500-char window after the import should have the scaffold_kind= kwarg
    window = agent_py[idx:idx + 700]
    assert "scaffold_kind=" in window, (
        "agent.py detect_progress_signals call missing scaffold_kind kwarg (Fix #33)"
    )
    assert "_target_scaffold" in window, (
        "agent.py detect_progress_signals must derive scaffold_kind from _target_scaffold"
    )


def main():
    tests = [
        test_react_default_preserves_app_tsx_advisory,
        test_gamedev_scaffold_advises_emit_design,
        test_gamedev_message_mentions_correct_deliverable,
        test_signal_name_unchanged_across_scaffolds,
        test_no_signal_when_writes_present,
        test_emit_design_counts_as_a_write,
        test_emit_design_prevents_long_stall,
        test_signal_fires_only_at_early_nudge_iter,
        test_agent_passes_scaffold_kind_to_progress,
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
