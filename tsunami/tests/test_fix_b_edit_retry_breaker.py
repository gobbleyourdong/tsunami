"""Pytest for FIX-B (JOB-INT-10) — file_edit retry-loop breaker.

Tests the agent-level `_fix_b_edit_failed` + `_current_content_snippet`
helpers directly without spinning up a full Agent.run() loop.
"""
from __future__ import annotations

import tempfile
import types
from pathlib import Path


def _make_agent_stub() -> object:
    """Build a minimal duck-typed object that carries the two helpers +
    the sink for `state.add_system_note`. Avoids Agent() ctor overhead."""
    from tsunami.agent import Agent
    agent = Agent.__new__(Agent)
    agent._edit_fail_count_by_path = {}
    notes: list[str] = []

    class _State:
        def add_system_note(self, msg: str) -> None:
            notes.append(msg)
    agent.state = _State()
    agent._notes = notes  # test hook
    return agent


def test_single_edit_failure_is_silent():
    """First failure on a path does NOT emit counter-signal."""
    agent = _make_agent_stub()
    agent._fix_b_edit_failed("/tmp/anything.json")
    assert agent._notes == []
    assert agent._edit_fail_count_by_path["/tmp/anything.json"] == 1


def test_two_consecutive_failures_fire_counter_signal():
    """Second failure on same path triggers the RETRY BREAKER note."""
    agent = _make_agent_stub()
    path = "/tmp/nonexistent_for_test.json"
    agent._fix_b_edit_failed(path)
    agent._fix_b_edit_failed(path)
    assert len(agent._notes) == 1
    note = agent._notes[0]
    assert "RETRY BREAKER" in note
    assert "FAILED 2x" in note
    assert "file_write" in note
    assert agent._edit_fail_count_by_path[path] == 2


def test_three_failures_emit_second_counter_signal():
    """Third failure also fires — doesn't go silent after the first warn."""
    agent = _make_agent_stub()
    path = "/tmp/still_failing.json"
    agent._fix_b_edit_failed(path)
    agent._fix_b_edit_failed(path)
    agent._fix_b_edit_failed(path)
    assert len(agent._notes) == 2
    assert "FAILED 3x" in agent._notes[1]


def test_counter_signal_includes_file_snippet():
    """When the file exists, the note carries actual bytes."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        fh.write('{"meta": {"title": "Sample"}, "cfg": {"x": 1}}')
        path = fh.name
    agent = _make_agent_stub()
    agent._fix_b_edit_failed(path)
    agent._fix_b_edit_failed(path)
    assert len(agent._notes) == 1
    assert '"title": "Sample"' in agent._notes[0] or "Sample" in agent._notes[0]
    Path(path).unlink(missing_ok=True)


def test_missing_file_still_emits_note_without_snippet():
    """File doesn't exist → snippet empty, note still fires."""
    agent = _make_agent_stub()
    agent._fix_b_edit_failed("/tmp/does_not_exist_abc123.json")
    agent._fix_b_edit_failed("/tmp/does_not_exist_abc123.json")
    assert len(agent._notes) == 1
    assert "RETRY BREAKER" in agent._notes[0]


def test_empty_path_is_noop():
    """Guard against empty path — do nothing, don't crash."""
    agent = _make_agent_stub()
    agent._fix_b_edit_failed("")
    assert agent._notes == []
    assert agent._edit_fail_count_by_path == {}


def test_snippet_truncates_to_max_chars():
    """Long files get truncated with ellipsis."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        fh.write("x" * 1000)
        path = fh.name
    agent = _make_agent_stub()
    snip = agent._current_content_snippet(path, max_chars=50)
    assert len(snip) <= 53  # 50 + "..."
    assert snip.endswith("...")
    Path(path).unlink(missing_ok=True)


def test_different_paths_track_independently():
    """Failures on distinct paths don't spill into each other's counters."""
    agent = _make_agent_stub()
    agent._fix_b_edit_failed("/tmp/path_a.json")
    agent._fix_b_edit_failed("/tmp/path_b.json")
    # Neither should fire yet (each at count 1).
    assert agent._notes == []
    assert agent._edit_fail_count_by_path["/tmp/path_a.json"] == 1
    assert agent._edit_fail_count_by_path["/tmp/path_b.json"] == 1
