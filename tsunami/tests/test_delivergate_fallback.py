"""Deliver-gate fallback — empty-text synthesis (tech-debt 97bd954 fix-b).

Standalone — no agent.py / model / eval dependencies. Safe to run while
the live eval holds ``/tmp/eval_tiered.lock``.

Exercises ``MessageResult.execute`` with an empty ``text`` arg, the shape
produced when ``#14 deliver-gate`` forces ``tool_choice=message_result``
(agent.py:1179) and the model complies with empty ``arguments``. Without
the fix, the tool prints a bare newline and records an empty tool-result;
with the fix, ``_synthesize_default_text`` materializes a delivery
message from the most-recent project under ``workspace_dir/deliverables``.
"""

from __future__ import annotations

import asyncio

import pytest

from tsunami.config import TsunamiConfig
from tsunami.tools import filesystem as fs_state
from tsunami.tools.message import MessageResult


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mk_tool(ws) -> MessageResult:
    cfg = TsunamiConfig(
        model_backend="api",
        model_name="test",
        model_endpoint="http://localhost:9999",
        workspace_dir=str(ws),
        max_iterations=5,
    )
    return MessageResult(cfg)


@pytest.fixture(autouse=True)
def _isolate_filesystem_globals():
    """_check_deliverable_complete reads fs_state._session_last_project and
    _last_written_deliverable. A prior test in the same pytest session can
    leave them set, which would route the gate at a stale project and mask
    the fallback. Snapshot + restore around every test in this file.
    """
    prev_slp = fs_state._session_last_project
    prev_lwd = fs_state._last_written_deliverable
    fs_state._session_last_project = None
    fs_state._last_written_deliverable = None
    try:
        yield
    finally:
        fs_state._session_last_project = prev_slp
        fs_state._last_written_deliverable = prev_lwd


def test_empty_text_synthesized_from_dist(tmp_path):
    """Empty ``text`` with a built deliverable → ``Build passed. App delivered at ...``.

    Matches the auto-deliver signature at ``agent.py:1734`` exactly so eval
    log-graders that grep for ``Build passed`` continue to hit.
    """
    proj = tmp_path / "deliverables" / "my-app"
    (proj / "dist").mkdir(parents=True)
    (proj / "dist" / "index.html").write_text("<!doctype html>")
    tool = _mk_tool(tmp_path)
    result = _run(tool.execute(text=""))
    assert not result.is_error
    assert "Build passed" in result.content
    assert "dist/index.html" in result.content
    assert "my-app" in result.content


def test_empty_text_no_dist_names_project(tmp_path):
    """Empty ``text`` with a half-built deliverable (no dist/) →
    ``Delivered <project>.`` — still names the work so logs aren't silent.
    """
    proj = tmp_path / "deliverables" / "half-built"
    proj.mkdir(parents=True)
    tool = _mk_tool(tmp_path)
    result = _run(tool.execute(text=""))
    assert not result.is_error
    assert "Delivered half-built" in result.content


def test_populated_text_passthrough(tmp_path):
    """Passthrough — when the model fills ``text`` normally, no synthesis
    happens and the content is delivered verbatim. Guards against the
    fallback clobbering legitimate messages.
    """
    proj = tmp_path / "deliverables" / "my-app"
    (proj / "dist").mkdir(parents=True)
    (proj / "dist" / "index.html").write_text("<!doctype html>")
    tool = _mk_tool(tmp_path)
    result = _run(tool.execute(text="Here's your thing."))
    assert not result.is_error
    assert result.content == "Here's your thing."
