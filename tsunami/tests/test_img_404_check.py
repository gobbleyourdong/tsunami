"""QA-1 Playtest Fire 117 + qa-solo dashboard regression: deliverables
shipped with `<img src="/icon-home">` references to sprites that were
never created. Browser 404s on page load.

Gate: for every `<img src="<literal>">` in App.tsx, verify the file
exists in the deliverable's public/ or src/assets/. Skip external
URLs / data URIs / variable refs.
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


def _make(tmp: str, name: str, app: str, assets=None) -> Path:
    ws = Path(tmp) / "workspace"
    d = ws / "deliverables" / name
    (d / "src").mkdir(parents=True)
    (d / "public").mkdir(parents=True)
    (d / "package.json").write_text(
        json.dumps({"name": "x", "dependencies": {"react": "19"}})
    )
    (d / "src" / "App.tsx").write_text(app)
    for a in (assets or []):
        (d / a).parent.mkdir(parents=True, exist_ok=True)
        (d / a).write_text("data")
    return ws


_PADDING_APP_TEMPLATE = (
    'import {{ useState }} from "react";\n'
    'export default function App() {{\n'
    '  const [c, setC] = useState(0);\n'
    '  return (\n'
    '    <div>\n'
    '      {IMG_TAG}\n'
    '      <h1>Dashboard</h1>\n'
    '      <p>Current count value: {{c}}</p>\n'
    '      <p>Some padding content for the length gate minimum.</p>\n'
    '      <button onClick={{() => setC(c + 1)}}>Increment</button>\n'
    '      <p>More padding here just to stay over 300 bytes cleanly.</p>\n'
    '    </div>\n'
    '  );\n'
    '}}\n'
)


def _app(img_tag: str) -> str:
    return _PADDING_APP_TEMPLATE.replace("{IMG_TAG}", img_tag)


def test_broken_img_src_blocks():
    """Fire 117 shape: `<img src="/icon-home">` with no matching file."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "dash", _app('<img src="/icon-home" alt="home"/>'))
        fs_state._session_last_project = "dash"
        fs_state._session_task_prompt = "dashboard"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "/icon-home" in r
        assert "404" in r


def test_valid_img_in_public_passes():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(
            tmp, "ok", _app('<img src="/logo.png" alt="logo"/>'),
            assets=["public/logo.png"],
        )
        fs_state._session_last_project = "ok"
        fs_state._session_task_prompt = "app with logo"
        assert _check_deliverable_complete(str(ws)) is None


def test_valid_img_in_src_assets_passes():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(
            tmp, "ok", _app('<img src="assets/icon.svg" alt="icon"/>'),
            assets=["src/assets/icon.svg"],
        )
        fs_state._session_last_project = "ok"
        fs_state._session_task_prompt = "app with icon"
        assert _check_deliverable_complete(str(ws)) is None


def test_external_img_passes():
    """External URLs are out of scope — user opt-in signal."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(
            tmp, "ok",
            _app('<img src="https://cdn.example.com/logo.png" alt="logo"/>'),
        )
        fs_state._session_last_project = "ok"
        fs_state._session_task_prompt = "app"
        assert _check_deliverable_complete(str(ws)) is None


def test_data_uri_img_passes():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(
            tmp, "ok",
            _app('<img src="data:image/png;base64,iVBORw0KGg..." alt="inline"/>'),
        )
        fs_state._session_last_project = "ok"
        fs_state._session_task_prompt = "app"
        assert _check_deliverable_complete(str(ws)) is None


def test_variable_src_passes():
    """`<img src={variable}>` — dynamic ref, not a literal; we can't
    verify without runtime evaluation. Skip."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  const iconUrl = "/never-exists.png";\n'
        '  return (\n'
        '    <div>\n'
        '      <img src={iconUrl} alt="dyn"/>\n'
        '      <h1>App</h1>\n'
        '      <p>{c}</p>\n'
        '      <button onClick={() => setC(c + 1)}>Click</button>\n'
        '      <p>Padding text for length requirement</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "var", app)
        fs_state._session_last_project = "var"
        fs_state._session_task_prompt = "app"
        assert _check_deliverable_complete(str(ws)) is None


def test_multiple_broken_imgs_listed():
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <img src="/icon-home" alt="h"/>\n'
        '      <img src="/icon-users" alt="u"/>\n'
        '      <img src="/icon-reports" alt="r"/>\n'
        '      <h1>Dashboard</h1>\n'
        '      <p>{c}</p>\n'
        '      <button onClick={() => setC(c + 1)}>Click</button>\n'
        '      <p>Padding line for length requirement</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "dash", app)
        fs_state._session_last_project = "dash"
        fs_state._session_task_prompt = "dashboard"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "3 broken asset" in r
        # At least the first one is named in the error.
        assert "/icon-home" in r


def test_non_img_src_passes():
    """Regression: `<iframe src>`, `<script src>`, etc. aren't this
    gate's concern — those go through other gates (outbound_exfil for
    external, HTML-element gate for script/iframe). Also: `<source>`
    tags inside <audio>/<video> aren't blocked here."""
    app = (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [c, setC] = useState(0);\n'
        '  return (\n'
        '    <div>\n'
        '      <audio controls>\n'
        '        <source src="/never-exists.mp3" type="audio/mpeg"/>\n'
        '      </audio>\n'
        '      <h1>Audio App</h1>\n'
        '      <p>Played: {c}</p>\n'
        '      <button onClick={() => setC(c + 1)}>Play</button>\n'
        '      <p>Padding content</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "audio", app)
        fs_state._session_last_project = "audio"
        fs_state._session_task_prompt = "audio player"
        # `<source src>` is not preceded by `<img` → our gate skips it.
        # Other gates (external URL checks) don't fire for relative paths.
        assert _check_deliverable_complete(str(ws)) is None


def test_img_with_protocol_relative_passes():
    """`<img src="//cdn/x">` — protocol-relative external, not a local 404."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(
            tmp, "ok",
            _app('<img src="//cdn.example.com/logo.png" alt="logo"/>'),
        )
        fs_state._session_last_project = "ok"
        fs_state._session_task_prompt = "app"
        # Other gates may flag this (outbound exfil check) but our img
        # gate specifically does NOT — protocol-relative is out of scope.
        r = _check_deliverable_complete(str(ws))
        if r:
            # If something else blocks, fine — but NOT our "no matching
            # file" error.
            assert "broken asset" not in r
