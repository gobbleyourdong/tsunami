"""QA-1 Playtest Fire 124: `text-statistics-tool/` shipped with a
`<textarea>` that had no `value` and no `onChange`. Typing into the
textarea couldn't reach React state; "real-time" stats stayed at 0
forever.

Gate: refuse `<textarea>` / text-type `<input>` with neither `value`
nor `onChange`. Skip: elements with `defaultValue` + `ref` (explicit
uncontrolled), non-text input types (submit/button/checkbox/radio/file).
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


def test_fire124_dead_textarea_blocks():
    """Fire 124 shape: textarea without value/onChange, stats hardcoded."""
    app = (
        'import React from "react";\n'
        'export default function App() {\n'
        '  const static_label = "analysis";\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Text Statistics</h1>\n'
        '      <textarea placeholder="Type here" rows={10} cols={50}/>\n'
        '      <p>Character count: 0</p>\n'
        '      <p>Word count: 0</p>\n'
        '      <p>Line count: 0</p>\n'
        '      <p>Static label: {static_label}</p>\n'
        '      <p>Padding content to pass the length requirement</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "stats", app)
        fs_state._session_last_project = "stats"
        fs_state._session_task_prompt = "text stats real-time"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "textarea" in r.lower() or "input" in r.lower()
        assert "onChange" in r


def test_controlled_textarea_passes():
    """Regression: real textarea with value + onChange passes."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [text, setText] = useState("");\n'
        '  const words = text.trim().split(/\\s+/).filter(Boolean).length;\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Text Statistics</h1>\n'
        '      <textarea value={text} onChange={e => setText(e.target.value)} rows={10}/>\n'
        '      <p>Words: {words}</p>\n'
        '      <p>Characters: {text.length}</p>\n'
        '      <p>More content for padding</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "ok", app)
        fs_state._session_last_project = "ok"
        fs_state._session_task_prompt = "text stats"
        assert _check_deliverable_complete(str(ws)) is None


def test_default_value_plus_ref_passes():
    """Explicit uncontrolled input with imperative ref is legit."""
    app = (
        'import { useState, useRef } from "react";\n'
        'export default function App() {\n'
        '  const ref = useRef(null);\n'
        '  const [count, setCount] = useState(0);\n'
        '  const measure = () => setCount(ref.current?.value.length || 0);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Measure Text</h1>\n'
        '      <textarea defaultValue="" ref={ref} rows={5}/>\n'
        '      <button onClick={measure}>Measure</button>\n'
        '      <p>Length: {count}</p>\n'
        '      <p>Padding</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "ref", app)
        fs_state._session_last_project = "ref"
        fs_state._session_task_prompt = "text measurement"
        assert _check_deliverable_complete(str(ws)) is None


def test_dead_text_input_blocks():
    """`<input type="text">` without value/onChange — same dead pattern."""
    app = (
        'import React from "react";\n'
        'export default function App() {\n'
        '  const placeholderValue = "search placeholder";\n'
        '  const resultsLabel = "No results yet to display for this query";\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Search Tool</h1>\n'
        '      <input type="text" placeholder={placeholderValue}/>\n'
        '      <p>Results: 0</p>\n'
        '      <p>Matches: 0</p>\n'
        '      <p>Total: 0</p>\n'
        '      <p>{resultsLabel}</p>\n'
        '      <p>More padding content to pass the 300-byte length gate</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "search", app)
        fs_state._session_last_project = "search"
        fs_state._session_task_prompt = "search app"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "value" in r or "onChange" in r


def test_submit_button_input_skipped():
    """`<input type="submit">` has a different interaction model — skip."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [name, setName] = useState("");\n'
        '  const handleSubmit = (e) => { e.preventDefault(); alert(name); };\n'
        '  return (\n'
        '    <form onSubmit={handleSubmit}>\n'
        '      <input value={name} onChange={e => setName(e.target.value)}/>\n'
        '      <input type="submit" value="Send"/>\n'
        '      <p>Current name: {name}</p>\n'
        '      <p>Padding content for length</p>\n'
        '    </form>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "form", app)
        fs_state._session_last_project = "form"
        fs_state._session_task_prompt = "form app"
        assert _check_deliverable_complete(str(ws)) is None


def test_checkbox_skipped():
    """Checkboxes use `checked` + `onChange` — different attr shape, skip."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [agreed, setAgreed] = useState(false);\n'
        '  const [name, setName] = useState("");\n'
        '  return (\n'
        '    <div>\n'
        '      <input value={name} onChange={e => setName(e.target.value)}/>\n'
        '      <input type="checkbox" checked={agreed} onChange={e => setAgreed(e.target.checked)}/>\n'
        '      <p>Agreed: {agreed ? "yes" : "no"}</p>\n'
        '      <p>Name: {name}</p>\n'
        '      <p>Padding line</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "cb", app)
        fs_state._session_last_project = "cb"
        fs_state._session_task_prompt = "agreement form"
        assert _check_deliverable_complete(str(ws)) is None


def test_ref_only_input_passes():
    """`<input ref={r}>` without value/onChange — imperative read, legit."""
    app = (
        'import { useRef, useState } from "react";\n'
        'export default function App() {\n'
        '  const ref = useRef(null);\n'
        '  const [name, setName] = useState("");\n'
        '  const grab = () => setName(ref.current.value);\n'
        '  return (\n'
        '    <div>\n'
        '      <input ref={ref} placeholder="enter name"/>\n'
        '      <button onClick={grab}>Grab</button>\n'
        '      <p>Grabbed: {name}</p>\n'
        '      <p>Padding content</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "ref2", app)
        fs_state._session_last_project = "ref2"
        fs_state._session_task_prompt = "grab input value"
        assert _check_deliverable_complete(str(ws)) is None


def test_password_input_dead_blocks():
    """`type="password"` still needs controlled/ref pattern."""
    app = (
        'import React from "react";\n'
        'export default function App() {\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Login</h1>\n'
        '      <input type="text" placeholder="username"/>\n'
        '      <input type="password" placeholder="password"/>\n'
        '      <button>Login</button>\n'
        '      <p>Session active: false</p>\n'
        '      <p>Padding content</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "login", app)
        fs_state._session_last_project = "login"
        fs_state._session_task_prompt = "login form"
        r = _check_deliverable_complete(str(ws))
        assert r is not None


def test_input_type_file_skipped():
    """`type="file"` — upload-specific, uses `files` not value/onChange."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [fname, setFname] = useState("");\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Upload</h1>\n'
        '      <input type="file" onChange={e => setFname(e.target.files?.[0]?.name || "")}/>\n'
        '      <p>Selected: {fname || "(none)"}</p>\n'
        '      <p>Padding line for length</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "up", app)
        fs_state._session_last_project = "up"
        fs_state._session_task_prompt = "file upload"
        assert _check_deliverable_complete(str(ws)) is None
