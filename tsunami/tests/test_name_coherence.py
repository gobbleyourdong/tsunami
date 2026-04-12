"""qa-solo Playtest (hello-world-button) — Fire 85 / 90 / 120 family:
deliverable names promise a primitive (button / form / table / etc.)
but the content drops it entirely. Gate: if the deliverable's name
contains an HTML-primitive keyword, the rendered JSX must actually
include that primitive.

Narrow keyword list keeps false-positive risk low — only matches
unambiguous whole-word keywords (so `platform` doesn't trip `form`).
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


# Long padded app shells so tests don't trip the 300-byte length gate.
def _app_no_button() -> str:
    return (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [count, setCount] = useState(0);\n'
        '  const [step, setStep] = useState(1);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Hello World App</h1>\n'
        '      <p>Counter shown below: {count}</p>\n'
        '      <p>Step increment: {step}</p>\n'
        '      <p>Interactive click not yet implemented in this demo version</p>\n'
        '      <input value={step} onChange={e => setStep(+e.target.value)}/>\n'
        '      <p>Additional content line for the delivery gate minimum</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )


def _app_with_button() -> str:
    return (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [count, setCount] = useState(0);\n'
        '  const [step, setStep] = useState(1);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Hello World App</h1>\n'
        '      <p>Counter: {count}</p>\n'
        '      <button onClick={() => setCount(count + step)}>Click me</button>\n'
        '      <p>Step: {step}</p>\n'
        '      <input value={step} onChange={e => setStep(+e.target.value)}/>\n'
        '      <p>Additional padding for the gate length check</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )


def test_hello_world_button_missing_button_blocks():
    """hello-world-button exact repro — no <button>, should refuse."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "hello-world-button", _app_no_button())
        fs_state._session_last_project = "hello-world-button"
        fs_state._session_task_prompt = "hello world button app"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "button" in r.lower()


def test_hello_world_button_with_button_passes():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "hello-world-button", _app_with_button())
        fs_state._session_last_project = "hello-world-button"
        fs_state._session_task_prompt = "hello world button app"
        assert _check_deliverable_complete(str(ws)) is None


def test_platform_app_without_form_passes():
    """Regression: `platform-app` should NOT trip `form` substring."""
    app = _app_with_button().replace("Hello World App", "Platform Dashboard")
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "platform-app", app)
        fs_state._session_last_project = "platform-app"
        fs_state._session_task_prompt = "platform app"
        # No <form> required because `platform` ≠ `form`.
        assert _check_deliverable_complete(str(ws)) is None


def test_contact_form_with_form_passes():
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [name, setName] = useState("");\n'
        '  const [email, setEmail] = useState("");\n'
        '  const submit = (e) => { e.preventDefault(); alert(name + email); };\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Contact Form</h1>\n'
        '      <form onSubmit={submit}>\n'
        '        <input value={name} onChange={e => setName(e.target.value)} placeholder="Name"/>\n'
        '        <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email"/>\n'
        '        <button type="submit">Send</button>\n'
        '      </form>\n'
        '      <p>Got: {name}</p>\n'
        '      <p>Padding content</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "contact-form", app)
        fs_state._session_last_project = "contact-form"
        fs_state._session_task_prompt = "contact form"
        assert _check_deliverable_complete(str(ws)) is None


def test_contact_form_without_form_blocks():
    """`contact-form` name without a `<form>` element."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [name, setName] = useState("");\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Contact Page</h1>\n'
        '      <input value={name} onChange={e => setName(e.target.value)}/>\n'
        '      <button onClick={() => alert(name)}>Send</button>\n'
        '      <p>Got: {name}</p>\n'
        '      <p>Just an input + button, no actual form element</p>\n'
        '      <p>More padding for the gate</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "contact-form", app)
        fs_state._session_last_project = "contact-form"
        fs_state._session_task_prompt = "contact form"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "form" in r.lower()


def test_transformer_pipeline_name_doesnt_trip_form():
    """`transformer-pipeline` name contains `form` as substring but
    whole-word boundary keeps it clean."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "transformer-pipeline", _app_with_button())
        fs_state._session_last_project = "transformer-pipeline"
        fs_state._session_task_prompt = "transformer pipeline"
        # No <form> required; the passing app has no <form>, should pass.
        assert _check_deliverable_complete(str(ws)) is None


def test_data_table_without_table_blocks():
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [rows, setRows] = useState([{id:1, name:"A"}, {id:2, name:"B"}]);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Data Table</h1>\n'
        '      {rows.map(r => <div key={r.id}>{r.name}</div>)}\n'
        '      <button onClick={() => setRows([...rows, {id:3, name:"C"}])}>Add</button>\n'
        '      <p>Rendered as divs instead of a proper table</p>\n'
        '      <p>Padding content</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "data-table", app)
        fs_state._session_last_project = "data-table"
        fs_state._session_task_prompt = "data table"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "table" in r.lower()


def test_todo_list_doesnt_trip_table():
    """`todo-list` → no table keyword in name — passes despite divs."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [items, setItems] = useState([]);\n'
        '  const [text, setText] = useState("");\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Todo List</h1>\n'
        '      <input value={text} onChange={e => setText(e.target.value)}/>\n'
        '      <button onClick={() => { setItems([...items, text]); setText(""); }}>Add</button>\n'
        '      {items.map((t, i) => <div key={i}>{t}</div>)}\n'
        '      <p>Padding line</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "todo-list", app)
        fs_state._session_last_project = "todo-list"
        fs_state._session_task_prompt = "todo list"
        assert _check_deliverable_complete(str(ws)) is None


def test_input_type_button_counts():
    """`<input type="button">` is equivalent to `<button>` for the check."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [count, setCount] = useState(0);\n'
        '  const [step, setStep] = useState(1);\n'
        '  const reset = () => setCount(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Button via Input Type</h1>\n'
        '      <input type="button" value="Click Me" onClick={() => setCount(count + step)}/>\n'
        '      <input type="button" value="Reset" onClick={reset}/>\n'
        '      <p>Current count: {count}</p>\n'
        '      <p>Step size: {step}</p>\n'
        '      <input value={step} onChange={e => setStep(+e.target.value)}/>\n'
        '      <p>Padding content for the gate length minimum requirement</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "my-button-demo", app)
        fs_state._session_last_project = "my-button-demo"
        fs_state._session_task_prompt = "button demo"
        assert _check_deliverable_complete(str(ws)) is None


def test_calc_without_any_primitive_word_passes():
    """Regression: names with no primitive keyword aren't checked at all."""
    app = _app_with_button()
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "my-calculator-app", app)
        fs_state._session_last_project = "my-calculator-app"
        fs_state._session_task_prompt = "calculator"
        assert _check_deliverable_complete(str(ws)) is None
