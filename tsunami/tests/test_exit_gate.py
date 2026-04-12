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
    """Phase 1 placeholder where the marker appears as user-visible text — REFUSED.

    Markers in comments are fine (QA-2 iter 23 false-positive, handled separately);
    markers in rendered JSX text signal the author really did ship a stub.
    """
    phase_app = """import { useState } from 'react'

export default function App() {
  const [v, setV] = useState(50)
  return (
    <div>
      <h1>Temperature Slider</h1>
      <input type="range" value={v} onChange={e => setV(+e.target.value)} />
      <p>Phase 1 layout complete. Content will go here in the next release.</p>
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


def test_marker_phrase_ignored_in_line_comment():
    """QA-2 iter 23: `// Phase 1: basic layout` in a comment while real code
    ships below should PASS. The marker check scans user-visible text only."""
    app = """import { useState } from 'react'

type Direction = 'Up' | 'Down'

export default function App() {
  const [count, setCount] = useState(0)
  const [dir, setDir] = useState<Direction>('Up')

  // Phase 1: Basic layout and state setup
  const handleClick = () => {
    if (dir === 'Up') setCount(count + 1)
    else setCount(count - 1)
  }
  const toggle = () => setDir(dir === 'Up' ? 'Down' : 'Up')

  return (
    <div>
      <h1>Directional Counter</h1>
      <p>Count: {count} Direction: {dir}</p>
      <button onClick={handleClick}>Click</button>
      <button onClick={toggle}>Toggle Direction</button>
    </div>
  )
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "directional-click-counter", app)
        fs_state.set_session_task_prompt("build a directional click counter with up and down")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert suffix == "", f"marker in comment should pass, got: {suffix!r}"


def test_marker_phrase_ignored_in_jsx_comment():
    """`{/* Placeholder for Phase 1 requirement met */}` in JSX should PASS."""
    app = """import { useState } from 'react'

export default function App() {
  const [n, setN] = useState(0)
  return (
    <div>
      <h1>Counter</h1>
      {/* Placeholder for Stats/Progress Bars (Phase 1 requirement met) */}
      <p>Value: {n}</p>
      <button onClick={() => setN(n + 1)}>Increment</button>
      <button onClick={() => setN(n - 1)}>Decrement</button>
      <button onClick={() => setN(0)}>Reset</button>
    </div>
  )
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "counter-app", app)
        fs_state.set_session_task_prompt("counter with plus minus reset")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert suffix == "", f"marker in JSX comment should pass, got: {suffix!r}"


def test_marker_phrase_ignored_in_block_comment():
    """`/* Phase 1: ... */` multi-line block comment should PASS when real code ships."""
    app = """import { useState } from 'react'

/*
 * Phase 1: basic layout
 * Phase 2: interactions (will go here)
 *
 * Done — full implementation below.
 */
export default function App() {
  const [value, setValue] = useState('hello world initial state')
  return (
    <div>
      <h1>Input Echo</h1>
      <input value={value} onChange={e => setValue(e.target.value)} />
      <p>You typed: {value}</p>
    </div>
  )
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "input-echo", app)
        fs_state.set_session_task_prompt("input echo build app that types input")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert suffix == "", f"marker in block comment should pass, got: {suffix!r}"


def test_typed_usestate_passes_static_skeleton_check():
    """QA-2 iter 18+23: `useState<number>(0)` is a real call — must not trip
    the `imports useState but never calls it` gate."""
    app = """import { useState } from 'react'

type Direction = 'Up' | 'Down'

export default function App() {
  const [count, setCount] = useState<number>(0)
  const [dir, setDir] = useState<Direction>('Up')
  return (
    <div>
      <h1>Typed Counter</h1>
      <p>Count: {count} ({dir})</p>
      <button onClick={() => setCount(count + 1)}>Up</button>
      <button onClick={() => setDir(dir === 'Up' ? 'Down' : 'Up')}>Flip</button>
    </div>
  )
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "typed-counter", app)
        fs_state.set_session_task_prompt("typed counter with up down direction")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert suffix == "", f"typed useState should count as called, got: {suffix!r}"


def test_untyped_usestate_still_passes():
    """Untyped `useState(0)` unchanged — regex keeps the existing behavior."""
    app = """import { useState } from 'react'

export default function App() {
  const [v, setV] = useState(5)
  return (
    <div>
      <h1>Plain Counter</h1>
      <p>Current count value: {v}. Click buttons to adjust.</p>
      <button onClick={() => setV(v + 1)}>Plus</button>
      <button onClick={() => setV(v - 1)}>Minus</button>
    </div>
  )
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "plain-counter", app)
        fs_state.set_session_task_prompt("plain counter with plus minus button")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert suffix == ""


def test_usestate_imported_never_called_still_blocks():
    """QA-2 iter 12 static-skeleton — import without any call (typed or otherwise)
    must still REFUSE. App is padded past 300 bytes to reach the useState gate."""
    app = """import { useState } from 'react'

// Imports useState but never calls it — renders hardcoded stats.
// This is the iter-12 text-statistics repro: looks like a React app
// but is actually completely static — no handlers, no state, nothing
// updates as the user types. The gate must still refuse this shape.
export default function App() {
  return (
    <div className="p-8 mx-auto max-w-2xl space-y-4 bg-neutral-900 text-white">
      <h1 className="text-3xl font-bold">Text Statistics</h1>
      <textarea placeholder="Type here..." className="w-full h-40 p-2" />
      <div className="grid grid-cols-3 gap-4">
        <div className="stat"><span>Chars:</span> <span>>0<</span></div>
        <div className="stat"><span>Words:</span> <span>>0<</span></div>
        <div className="stat"><span>Lines:</span> <span>>0<</span></div>
      </div>
    </div>
  )
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "text-stats", app)
        fs_state.set_session_task_prompt("text statistics tool with live update counts")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert "REFUSED" in suffix
        assert "useState" in suffix


def test_all_task_complete_returns_call_exit_gate():
    """QA-1 Fire 33: the delivery-deadline safety valve reaches the normal
    task_complete return without ever entering message_result's gate.
    Source-invariant check that every return path inside agent.run's loop
    either goes through message_result (which runs its own gate) or
    appends _exit_gate_suffix() to the return string.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "agent.py").read_text()

    # Common task_complete return must append the gate suffix (catches the
    # delivery-deadline safety valve path, which sets task_complete=True +
    # breaks without calling message_result).
    assert "return result + self._exit_gate_suffix()" in src, (
        "normal task_complete return must append _exit_gate_suffix() — "
        "otherwise delivery-deadline path ships placeholders silently"
    )

    # The three original forced-exit paths from 4ade0cf must also call it.
    exit_calls = src.count("self._exit_gate_suffix()")
    assert exit_calls >= 4, (
        f"expected _exit_gate_suffix() called on all 4 exit paths "
        f"(safety valve / hard cap / abort / task_complete); found {exit_calls}"
    )


def test_marker_phrase_still_blocks_in_rendered_text():
    """User-visible `<p>Phase 1 complete!</p>` SHOULD still REFUSE —
    that's authorial intent in prose, not a comment."""
    app = """import { useState } from 'react'

export default function App() {
  const [n, setN] = useState(0)
  return (
    <div>
      <h1>Status</h1>
      <p>Phase 1 complete! Interactive features coming soon.</p>
      <button onClick={() => setN(n + 1)}>Click: {n}</button>
    </div>
  )
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        _scaffold_deliverable(tmp, "status-page", app)
        fs_state.set_session_task_prompt("status page with counter")
        agent = _make_agent(tmp)
        suffix = agent._exit_gate_suffix()
        assert "REFUSED" in suffix
        # Should specifically mention the marker found
        assert "phase 1" in suffix.lower() or "coming soon" in suffix.lower()
