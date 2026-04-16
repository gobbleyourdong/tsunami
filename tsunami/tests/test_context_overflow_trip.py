"""Site A context_overflow trip handler — unit coverage for the extracted
helper ``Agent._on_context_overflow_trip``.

The inline block at agent.py:~1205 used to duplicate ``_on_read_spiral_trip``'s
shape for "signature parity with 4a08316". The debt-instance refactor
extracted it into a method and this file pins the method's contract: log
lines, return strings, and state mutations are byte-identical to the
pre-refactor inline behavior.

We exercise the method on a ``SimpleNamespace`` stand-in rather than a
full ``Agent`` instance — the helper only reads ``self.config.workspace_dir``
and ``self.state.iteration``, and mutates ``self.state.task_complete`` and
``self._tool_history``. No need to spin up the model client, registries,
or watcher for a sync filesystem+log helper.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from tsunami.agent import Agent


def _fake(workspace_dir, iteration: int = 5):
    """Minimal stand-in for ``self`` — just the attributes the helper reads."""
    return SimpleNamespace(
        config=SimpleNamespace(workspace_dir=str(workspace_dir)),
        state=SimpleNamespace(iteration=iteration, task_complete=False),
        _tool_history=[],
    )


def test_dist_exists_returns_delivered_message_and_marks_complete(tmp_path, caplog):
    proj = tmp_path / "deliverables" / "my-app"
    (proj / "dist").mkdir(parents=True)
    (proj / "dist" / "index.html").write_text("<!doctype html>")
    fake = _fake(tmp_path, iteration=17)

    caplog.set_level(logging.WARNING)
    result = Agent._on_context_overflow_trip(fake, consecutive_errors=3)

    assert result == "Build delivered at my-app/dist after context overflow."
    assert fake.state.task_complete is True
    assert fake._tool_history == ["message_result"]
    # Byte-identical loop_exit log signature from 4a08316
    assert any(
        "loop_exit path=context_overflow_exit" in r.message
        and "turn=17" in r.message
        and "dist=my-app/dist" in r.message
        for r in caplog.records
    ), f"missing dist-exit signature; got {[r.message for r in caplog.records]}"


def test_no_dist_returns_no_dist_message(tmp_path, caplog):
    """Deliverables dir exists with a project but no dist/ yet."""
    (tmp_path / "deliverables" / "half-built").mkdir(parents=True)
    fake = _fake(tmp_path, iteration=9)

    caplog.set_level(logging.WARNING)
    result = Agent._on_context_overflow_trip(fake, consecutive_errors=4)

    assert result == "Context overflow after 4 400s, no dist available."
    assert fake.state.task_complete is False  # NOT set when no dist
    assert fake._tool_history == []
    assert any(
        "loop_exit path=context_overflow_no_dist" in r.message and "turn=9" in r.message
        for r in caplog.records
    )


def test_no_deliverables_dir_returns_no_dist_message(tmp_path, caplog):
    """workspace_dir has no deliverables/ at all."""
    fake = _fake(tmp_path, iteration=2)

    caplog.set_level(logging.WARNING)
    result = Agent._on_context_overflow_trip(fake, consecutive_errors=5)

    assert result == "Context overflow after 5 400s, no dist available."
    assert fake.state.task_complete is False
    assert any("loop_exit path=context_overflow_no_dist" in r.message for r in caplog.records)


def test_picks_newest_project_by_mtime(tmp_path, caplog):
    """When multiple projects exist, pick the one with the newest mtime.
    Same mtime-sort rule as the pre-refactor inline block."""
    old = tmp_path / "deliverables" / "old-app"
    (old / "dist").mkdir(parents=True)
    (old / "dist" / "index.html").write_text("<!doctype html>")
    new = tmp_path / "deliverables" / "new-app"
    (new / "dist").mkdir(parents=True)
    (new / "dist" / "index.html").write_text("<!doctype html>")
    # Force ordering via mtime: touch new-app LAST
    (new / "dist" / "index.html").touch()

    fake = _fake(tmp_path)
    result = Agent._on_context_overflow_trip(fake, consecutive_errors=3)

    assert "new-app" in result
    assert "old-app" not in result


def test_consecutive_errors_formatted_in_no_dist_message(tmp_path):
    fake = _fake(tmp_path)
    r = Agent._on_context_overflow_trip(fake, consecutive_errors=12)
    assert "after 12 400s" in r
