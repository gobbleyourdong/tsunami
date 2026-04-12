"""Agent-exit gate — forced-exit paths run content gates.

Context: QA-1 Fire 17+27 called this out as the single highest-leverage
pending fix. When the agent exits via safety valve / hard cap / abort,
it bypasses message_result's content gates — so placeholder deliverables
ship silently. This verifies the gate fires on those paths too.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tsunami.agent import Agent
from tsunami.config import TsunamiConfig
from tsunami.tools import filesystem as fs_state


_PLACEHOLDER_APP_TSX = (
    '// TODO: Replace with your app\n'
    'export default function App() {\n'
    '  return <div>Loading...</div>\n'
    '}\n'
)

_REAL_APP_TSX = """import { useState } from 'react'

export default function App() {
  const [count, setCount] = useState(0)
  return (
    <div>
      <h1>Counter</h1>
      <button onClick={() => setCount(count + 1)}>Increment {count}</button>
      <button onClick={() => setCount(count - 1)}>Decrement</button>
      <button onClick={() => setCount(0)}>Reset</button>
    </div>
  )
}
"""


def _make_agent(workspace: str) -> Agent:
    cfg = TsunamiConfig(
        model_backend="api",
        model_name="test",
        model_endpoint="http://localhost:9999",
        workspace_dir=workspace,
        max_iterations=5,
    )
    return Agent(cfg)


def _scaffold_deliverable(workspace: str, name: str, app_content: str) -> Path:
    deliv = Path(workspace) / "deliverables" / name
    (deliv / "src").mkdir(parents=True, exist_ok=True)
    (deliv / "package.json").write_text('{"name": "' + name + '"}')
    (deliv / "src" / "App.tsx").write_text(app_content)
    fs_state.register_session_project(name)
    fs_state.set_session_task_prompt("build me a counter with plus minus reset")
    return deliv


@pytest.fixture(autouse=True)
def reset_session_state():
    fs_state._session_created_projects.clear()
    fs_state._session_last_project = None
    fs_state._session_task_prompt = ""
    yield
    fs_state._session_created_projects.clear()
    fs_state._session_last_project = None
    fs_state._session_task_prompt = ""


def test_exit_gate_flags_scaffold_placeholder():
    """Unchanged scaffold placeholder → REFUSED surfaced in exit message."""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "counter-app", _PLACEHOLDER_APP_TSX)
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert "REFUSED" in suffix, f"expected REFUSED in suffix, got: {suffix!r}"
        assert "counter-app" in suffix


def test_exit_gate_flags_short_app():
    """Under-300-byte App.tsx → REFUSED."""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "tiny-app", "export default () => <div>hi</div>\n")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert "REFUSED" in suffix
        assert "too short" in suffix or "only" in suffix


def test_exit_gate_passes_real_app():
    """Real App.tsx with useState + handlers and matching prompt → empty suffix."""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "counter-app", _REAL_APP_TSX)
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert suffix == "", f"expected pass, got: {suffix!r}"


def test_exit_gate_empty_workspace_returns_empty():
    """No deliverable → empty suffix (don't block non-React exits)."""
    with tempfile.TemporaryDirectory() as tmp:
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert suffix == ""


def test_exit_gate_flags_phase_marker():
    """Phase 1 placeholder (QA-2 iter 21 pattern) → REFUSED."""
    phase_app = """import { useState } from 'react'

// Phase 1: Basic layout setup
export default function App() {
  const [v, setV] = useState(50)
  return (
    <div>
      <h1>Temperature Slider</h1>
      <input type="range" value={v} onChange={e => setV(+e.target.value)} />
      {/* Content will go here in Phase 2 */}
    </div>
  )
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "temp-slider", phase_app)
        fs_state.set_session_task_prompt("build a temperature slider cold mild hot")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert "REFUSED" in suffix
        assert "will go here" in suffix or "placeholder" in suffix.lower()


def test_exit_gate_handles_exceptions_silently():
    """If the gate raises, suffix is empty — don't break the exit path."""
    with tempfile.TemporaryDirectory() as tmp:
        agent = _make_agent(tmp)
        # Forcibly break workspace resolution
        agent.config.workspace_dir = "/nonexistent/\x00/path"
        suffix = agent._exit_gate_suffix()
        assert suffix == ""
