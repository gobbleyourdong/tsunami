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


def test_empty_text_no_deliverables_dir(tmp_path):
    """Empty ``text`` with no ``deliverables/`` at all (api-only scaffold
    or brand-new session) → bare ``Delivered.``. Guards against the
    path-walk crashing on missing directories."""
    tool = _mk_tool(tmp_path)
    result = _run(tool.execute(text=""))
    assert not result.is_error
    assert result.content == "Delivered."


def test_empty_text_deliverables_dir_is_empty(tmp_path):
    """Empty ``text`` with ``deliverables/`` present but no projects
    inside → bare ``Delivered.`` (mtime-sort of nothing must not IndexError).
    Previously the ``for proj in projects[:1]:`` idiom hid this case; make
    the zero-project fall-through explicit."""
    (tmp_path / "deliverables").mkdir()
    tool = _mk_tool(tmp_path)
    result = _run(tool.execute(text=""))
    assert not result.is_error
    assert result.content == "Delivered."


def test_empty_text_uses_fs_state_accessor(tmp_path):
    """When ``fs_state.get_effective_target_project()`` identifies the
    session's active project, synthesis MUST target that project — not
    the mtime-newest one. Prevents a late-touched sibling (e.g.,
    ``.context/`` cache or a neighbour dir) from shadowing the real
    deliverable the agent intended to ship.
    """
    newest = tmp_path / "deliverables" / "zz-neighbour"
    (newest / "dist").mkdir(parents=True)
    (newest / "dist" / "index.html").write_text("<!doctype html>")
    active = tmp_path / "deliverables" / "my-app"
    (active / "dist").mkdir(parents=True)
    (active / "dist" / "index.html").write_text("<!doctype html>")
    # Touch newest LAST so mtime-sort would pick it
    (newest / "dist" / "index.html").touch()

    fs_state._session_last_project = "my-app"
    tool = _mk_tool(tmp_path)
    result = _run(tool.execute(text=""))
    assert not result.is_error
    assert "my-app" in result.content
    assert "zz-neighbour" not in result.content


def test_empty_text_fs_state_name_missing_falls_back_to_mtime(tmp_path):
    """If ``fs_state.get_effective_target_project()`` names a project that
    no longer exists on disk (stale state), fall back to mtime-sort rather
    than erroring."""
    proj = tmp_path / "deliverables" / "real-proj"
    proj.mkdir(parents=True)
    fs_state._session_last_project = "ghost-proj"  # does not exist
    tool = _mk_tool(tmp_path)
    result = _run(tool.execute(text=""))
    assert not result.is_error
    assert "Delivered real-proj" in result.content
