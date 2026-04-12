"""QA-1 Playtest Fires 117 + 119: dashboard and analytics-dashboard-charts
shipped with `<a href="#">` "tabs" that had no onClick — cosmetic nav
that looks interactive but does nothing. Three+ such anchors in a file
is a signature of the agent copy-pasting a nav bar without wiring it.

Gate: 2+ `<a href="#">` (or `<a href="">`) without onClick → REFUSE.
Single dead anchor passes (back-to-top convention). Anchors with
onClick pass. External hrefs pass.
"""

from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path

from tsunami.tools.message import _check_deliverable_complete
from tsunami.tools import filesystem as fs_state


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


def _make(tmp: str, name: str, app: str) -> Path:
    ws = Path(tmp) / "workspace"
    d = ws / "deliverables" / name
    (d / "src").mkdir(parents=True)
    (d / "package.json").write_text(
        json.dumps({"name": "x", "dependencies": {"react": "19"}})
    )
    (d / "src" / "App.tsx").write_text(app)
    return ws


def test_fire119_three_dead_anchors_blocks():
    """Fire 119: Overview / Reports / Settings as cosmetic nav tabs."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Analytics Dashboard</h1>\n'
        '      <nav>\n'
        '        <a href="#">Overview</a>\n'
        '        <a href="#">Reports</a>\n'
        '        <a href="#">Settings</a>\n'
        '      </nav>\n'
        '      <p>Count: {c}</p>\n'
        '      <button onClick={() => setC(c + 1)}>Increment</button>\n'
        '      <p>Padding content for the length requirement</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "dash", app)
        fs_state._session_last_project = "dash"
        fs_state._session_task_prompt = "analytics dashboard"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "3" in r and "onClick" in r


def test_single_dead_anchor_passes():
    """Back-to-top convention uses a single `<a href="#">` — that's legit."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>App</h1>\n'
        '      <p>Count: {c}</p>\n'
        '      <button onClick={() => setC(c + 1)}>Click</button>\n'
        '      <a href="#">Back to top</a>\n'
        '      <p>Padding content line for the gate length check</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "ok", app)
        fs_state._session_last_project = "ok"
        fs_state._session_task_prompt = "counter app"
        assert _check_deliverable_complete(str(ws)) is None


def test_wired_anchors_pass():
    """`<a href="#" onClick={handler}>` is a valid React pattern."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Wired Nav</h1>\n'
        '      <a href="#" onClick={e => { e.preventDefault(); setC(0); }}>Home</a>\n'
        '      <a href="#" onClick={e => { e.preventDefault(); setC(c + 1); }}>Inc</a>\n'
        '      <a href="#" onClick={e => { e.preventDefault(); setC(c - 1); }}>Dec</a>\n'
        '      <p>Count: {c}</p>\n'
        '      <p>Some padding text</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "wired", app)
        fs_state._session_last_project = "wired"
        fs_state._session_task_prompt = "counter with nav"
        assert _check_deliverable_complete(str(ws)) is None


def test_external_hrefs_pass():
    """`<a href="https://...">` is real navigation — not cosmetic."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Links</h1>\n'
        '      <a href="https://example.com">External 1</a>\n'
        '      <a href="https://other.com">External 2</a>\n'
        '      <a href="https://third.com">External 3</a>\n'
        '      <p>Count: {c}</p>\n'
        '      <button onClick={() => setC(c + 1)}>Click</button>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "ext", app)
        fs_state._session_last_project = "ext"
        fs_state._session_task_prompt = "links app"
        assert _check_deliverable_complete(str(ws)) is None


def test_two_dead_anchors_blocks():
    """Exactly 2 dead anchors — threshold met, should refuse."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <a href="#">Tab 1</a>\n'
        '      <a href="#">Tab 2</a>\n'
        '      <h1>App</h1>\n'
        '      <p>Count: {c}</p>\n'
        '      <button onClick={() => setC(c + 1)}>Click</button>\n'
        '      <p>Padding text</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "tab", app)
        fs_state._session_last_project = "tab"
        fs_state._session_task_prompt = "tabbed app"
        r = _check_deliverable_complete(str(ws))
        assert r is not None


def test_empty_href_anchors_also_block():
    """`<a href="">` (no fragment) is equally cosmetic."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <a href="">Foo</a>\n'
        '      <a href="">Bar</a>\n'
        '      <a href="">Baz</a>\n'
        '      <h1>App</h1>\n'
        '      <p>{c}</p>\n'
        '      <button onClick={() => setC(c + 1)}>Click</button>\n'
        '      <p>Padding line</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "empty", app)
        fs_state._session_last_project = "empty"
        fs_state._session_task_prompt = "app"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
