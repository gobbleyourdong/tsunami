"""build_system_prompt: hide existing-projects list on fresh builds.

QA-1 Fire 25 traced the "wrong-deliverable" pathology to the
`Existing projects (...)` line: on a fresh prompt the model saw recent
deliverables and was pulled toward modifying one instead of creating new.
`hide_existing_projects=True` makes that line disappear. Iteration mode
still keeps it (when the agent explicitly loaded an active project the
context is elsewhere anyway, but the list remains visible in case the
model wants to navigate).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tsunami.prompt import build_system_prompt
from tsunami.state import AgentState


def _scaffold(workspace: str, names):
    for name in names:
        (Path(workspace) / "deliverables" / name / "src").mkdir(parents=True, exist_ok=True)
        (Path(workspace) / "deliverables" / name / "package.json").write_text(
            '{"name": "' + name + '"}'
        )


def test_existing_projects_shown_by_default():
    """Default (iteration mode): list is visible."""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold(tmp, ["counter-app", "todo-list"])
        state = AgentState()
        prompt = build_system_prompt(state, workspace=tmp, lite=True)
        assert "Existing projects" in prompt
        assert "counter-app" in prompt
        assert "todo-list" in prompt


def test_hide_existing_projects_removes_list():
    """Fresh-build mode: list is suppressed (Fire 25 fix)."""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold(tmp, ["counter-app", "todo-list"])
        state = AgentState()
        prompt = build_system_prompt(
            state, workspace=tmp, lite=True, hide_existing_projects=True
        )
        assert "Existing projects" not in prompt
        assert "counter-app" not in prompt
        assert "todo-list" not in prompt


def test_hide_does_nothing_when_no_projects():
    """No deliverables dir → both flags produce the same prompt."""
    with tempfile.TemporaryDirectory() as tmp:
        state = AgentState()
        p1 = build_system_prompt(state, workspace=tmp, lite=True)
        p2 = build_system_prompt(
            state, workspace=tmp, lite=True, hide_existing_projects=True
        )
        assert "Existing projects" not in p1
        assert "Existing projects" not in p2


def test_agent_run_passes_hide_flag_on_fresh_build():
    """Source-invariant: agent.run must pass hide_existing_projects based on
    the existing_context result so the Fire 25 bleed path stays closed."""
    src = (Path(__file__).resolve().parent.parent / "agent.py").read_text()
    assert "hide_existing_projects=is_fresh_build" in src, (
        "agent.run must forward the fresh-build signal to build_system_prompt"
    )
    # _detect_existing_project must be called BEFORE build_system_prompt so
    # we know whether to hide.
    detect_idx = src.find("existing_context = self._detect_existing_project(user_message)")
    build_idx = src.find("system_prompt = build_system_prompt(")
    assert detect_idx != -1 and build_idx != -1
    assert detect_idx < build_idx, (
        "_detect_existing_project must run before build_system_prompt so "
        "is_fresh_build is known when building the prompt"
    )
