"""QA-3 Fire 79: workspace/ root writes are blocked.

Agents should put all output inside workspace/deliverables/<name>/. A bare
`workspace/qa3_marker.txt` plant is a prompt-injection vector (next session
sees the file and may act on its content). Block bare NEW-file writes to
the workspace root; existing files (legacy shell scripts etc.) are untouched
so edits to them still pass.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tsunami.tools.filesystem import _is_safe_write
from tsunami.tools import filesystem as fs_state


@pytest.fixture(autouse=True)
def reset_session_state():
    fs_state._session_created_projects.clear()
    yield
    fs_state._session_created_projects.clear()


def _make_workspace():
    """Build a tmp workspace with the usual subdirs."""
    tmp = tempfile.mkdtemp()
    (Path(tmp) / "workspace").mkdir()
    (Path(tmp) / "workspace" / "deliverables").mkdir()
    (Path(tmp) / "workspace" / ".observations").mkdir()
    return str(Path(tmp) / "workspace")


def test_blocks_bare_file_at_workspace_root():
    """QA-3 Fire 79 exact repro: file_write to workspace/qa3_marker.txt blocks."""
    ws = _make_workspace()
    target = Path(ws) / "qa3_marker.txt"
    result = _is_safe_write(target, ws)
    assert result is not None
    assert "BLOCKED" in result
    assert "workspace/" in result


def test_blocks_bare_tsx_at_workspace_root():
    """Any filename at workspace root — not just .txt — blocks."""
    ws = _make_workspace()
    target = Path(ws) / "App.tsx"
    result = _is_safe_write(target, ws)
    assert result is not None
    assert "BLOCKED" in result


def test_allows_write_inside_deliverable():
    """Legit: writes inside workspace/deliverables/<name>/ pass."""
    ws = _make_workspace()
    fs_state.register_session_project("my-app")
    (Path(ws) / "deliverables" / "my-app" / "src").mkdir(parents=True)
    target = Path(ws) / "deliverables" / "my-app" / "src" / "App.tsx"
    result = _is_safe_write(target, ws)
    assert result is None


def test_allows_write_inside_observations():
    """Legit: .observations/*.jsonl (observer-owned) passes."""
    ws = _make_workspace()
    target = Path(ws) / ".observations" / "observations.jsonl"
    result = _is_safe_write(target, ws)
    assert result is None


def test_allows_write_inside_memory():
    """Legit: .memory/ (memory-extract-owned) passes — subdir of workspace, not bare root."""
    ws = _make_workspace()
    (Path(ws) / ".memory").mkdir()
    target = Path(ws) / ".memory" / "user_profile.md"
    result = _is_safe_write(target, ws)
    assert result is None


def test_allows_edit_of_existing_workspace_root_file():
    """Legit: editing an existing workspace/ root file (legacy shell script /
    doc) still passes — only NEW file creation at root is blocked, to avoid
    breaking legitimate pre-existing files that agents sometimes need to edit."""
    ws = _make_workspace()
    existing = Path(ws) / "check_server.sh"
    existing.write_text("#!/bin/bash\necho ok\n")
    result = _is_safe_write(existing, ws)
    # Existing file — should pass the workspace-root block
    assert result is None or "workspace/ root" not in result
