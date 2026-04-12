"""QA-1 Playtest Fire 117/119: delivery gate targeted wrong project.

Root cause: agent wrote App.tsx without a preceding project_init (or the
session had no ProjectInit at all). `_session_last_project` stayed None.
The gate fell back to max-mtime, which picked a neighbour's deliverable
(e.g. a clean 96-byte scaffold from a QA-3 probe). That passed the
gate, so the REAL deliverable — which had "Phase 1: Basic layout
complete. Ready for charts." in JSX text — shipped unchecked.

Fix: track the deliverable that received the LAST successful
file_write / file_edit / file_append. When ProjectInit hasn't run
(`_session_last_project` None), use that as the second fallback
BEFORE max-mtime. Most reliable signal that "this is the project
being actively worked on right now".
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tsunami.tools.filesystem import (
    _note_write_to_deliverable,
    get_effective_target_project,
)
from tsunami.tools import filesystem as fs_state
from tsunami.tools.message import _check_deliverable_complete


@pytest.fixture(autouse=True)
def reset_state():
    fs_state._session_created_projects.clear()
    fs_state._session_last_project = None
    fs_state._last_written_deliverable = None
    fs_state._session_task_prompt = ""
    fs_state._active_project = None
    yield
    fs_state._session_created_projects.clear()
    fs_state._session_last_project = None
    fs_state._last_written_deliverable = None
    fs_state._session_task_prompt = ""
    fs_state._active_project = None


def _make_workspace(tmp: str) -> Path:
    ws = Path(tmp) / "workspace"
    (ws / "deliverables").mkdir(parents=True)
    return ws


def _make_deliverable(ws: Path, name: str, app_content: str):
    d = ws / "deliverables" / name
    (d / "src").mkdir(parents=True)
    (d / "package.json").write_text('{"name": "x"}')
    (d / "src" / "App.tsx").write_text(app_content)
    return d


def test_note_write_records_deliverable_name():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_workspace(tmp)
        _make_deliverable(ws, "my-project", "// placeholder")
        p = (ws / "deliverables" / "my-project" / "src" / "App.tsx").resolve()
        _note_write_to_deliverable(p, str(ws))
        assert fs_state._last_written_deliverable == "my-project"


def test_note_write_outside_deliverables_is_noop():
    """A write to `workspace/scratch.txt` should NOT set the tracker."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_workspace(tmp)
        p = (ws / "scratch.txt").resolve()
        _note_write_to_deliverable(p, str(ws))
        assert fs_state._last_written_deliverable is None


def test_effective_target_prefers_session_last_project():
    """_session_last_project is higher priority than _last_written_deliverable."""
    fs_state._session_last_project = "project-a"
    fs_state._last_written_deliverable = "project-b"
    assert get_effective_target_project() == "project-a"


def test_effective_target_falls_back_to_last_written():
    fs_state._session_last_project = None
    fs_state._last_written_deliverable = "project-b"
    assert get_effective_target_project() == "project-b"


def test_effective_target_none_when_both_unset():
    fs_state._session_last_project = None
    fs_state._last_written_deliverable = None
    assert get_effective_target_project() is None


def test_fire119_gate_catches_phase_marker_via_write_tracker():
    """Fire 119 repro: agent writes App.tsx with `Phase 1: ...` text but
    doesn't call project_init. Gate should still target the right project
    via _last_written_deliverable fallback."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_workspace(tmp)
        # Neighbor (max-mtime after creation) — clean scaffold, would pass
        # the gate if mtime-fallback picked it.
        _make_deliverable(ws, "neighbor", "import { useState } from 'react';\n"
                                           "export default function App() {\n"
                                           "  const [c, setC] = useState(0);\n"
                                           "  return <button onClick={() => setC(c+1)}>{c}</button>;\n"
                                           "}\n")
        # Real project, written last but not registered via project_init.
        phase_app = (
            'import React from "react";\n'
            'export default function App() {\n'
            '  return (\n'
            '    <div>\n'
            '      <h1>Analytics Dashboard</h1>\n'
            '      <div>Phase 1: Basic layout complete. Ready for charts.</div>\n'
            '    </div>\n'
            '  );\n'
            '}\n'
        )
        _make_deliverable(ws, "analytics-dashboard-charts", phase_app)
        # Agent's file_write noted it — but no ProjectInit.
        p = (ws / "deliverables" / "analytics-dashboard-charts" / "src" / "App.tsx").resolve()
        _note_write_to_deliverable(p, str(ws))
        fs_state._session_task_prompt = "build an analytics dashboard with charts"

        result = _check_deliverable_complete(str(ws))
        assert result is not None, "gate should refuse, got None (pass)"
        assert "analytics-dashboard-charts" in result
        assert "Phase 1" in result or "phase" in result.lower()


def test_project_init_still_wins_over_write_tracker():
    """Regression: if ProjectInit ran, its name must still win."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_workspace(tmp)
        real = (
            'import { useState } from "react";\n'
            'export default function App() {\n'
            '  const [c, setC] = useState(0);\n'
            '  const [step, setStep] = useState(1);\n'
            '  const inc = () => setC(c + step);\n'
            '  const dec = () => setC(c - step);\n'
            '  const reset = () => setC(0);\n'
            '  return (\n'
            '    <div>\n'
            '      <h1>Counter App</h1>\n'
            '      <p>Value: {c}</p>\n'
            '      <button onClick={inc}>+</button>\n'
            '      <button onClick={dec}>-</button>\n'
            '      <button onClick={reset}>Reset</button>\n'
            '      <input type="number" value={step} onChange={e => setStep(+e.target.value)}/>\n'
            '    </div>\n'
            '  );\n'
            '}\n'
        )
        _make_deliverable(ws, "intended", real)
        _make_deliverable(ws, "stale", "// Phase 1 placeholder\nexport default function App() { return <div/>; }\n")
        # Agent's `_last_written_deliverable` points to a STALE project
        # (simulating an earlier write in the session) — but ProjectInit
        # ran more recently and set _session_last_project to the intended.
        fs_state._last_written_deliverable = "stale"
        fs_state._session_last_project = "intended"
        fs_state._session_task_prompt = "build a counter app"

        result = _check_deliverable_complete(str(ws))
        # Gate should target `intended` and pass (clean app), not `stale`.
        assert result is None, f"gate should pass, got: {result}"


def test_mtime_fallback_still_works_when_all_trackers_empty():
    """When neither _session_last_project nor _last_written_deliverable
    is set, the original max-mtime fallback still runs."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make_workspace(tmp)
        _make_deliverable(
            ws, "only",
            'import { useState } from "react";\n'
            'export default function App() {\n'
            '  const [c, setC] = useState(0);\n'
            '  const [step, setStep] = useState(1);\n'
            '  const inc = () => setC(c + step);\n'
            '  const dec = () => setC(c - step);\n'
            '  const reset = () => setC(0);\n'
            '  return (\n'
            '    <div>\n'
            '      <h1>Counter App</h1>\n'
            '      <p>Value: {c}</p>\n'
            '      <button onClick={inc}>+</button>\n'
            '      <button onClick={dec}>-</button>\n'
            '      <button onClick={reset}>Reset</button>\n'
            '      <input type="number" value={step} onChange={e => setStep(+e.target.value)}/>\n'
            '    </div>\n'
            '  );\n'
            '}\n',
        )
        fs_state._session_task_prompt = "counter app with plus minus reset"
        # Both trackers empty — fallback selects `only` by mtime.
        result = _check_deliverable_complete(str(ws))
        # `only` passes cleanly.
        assert result is None
