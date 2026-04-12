"""QA-1 Playtest Fire 121: `regex-tester-input/` shipped with
`/^(a+)+$/` — catastrophic-backtracking regex (ReDoS). Input like
"aaaaaaaaaaaaab" hangs the browser for seconds / minutes (exponential
time complexity).

Gate: block nested-quantifier regex patterns in App.tsx source — the
classic `(<group>+)+` / `(<group>*)*` / `(<group>+)*` / `(<group>*)+`
shapes. These are almost always a misunderstanding of regex semantics;
legit use is vanishingly rare.
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


def _padded_app(regex_literal: str) -> str:
    """App shell with enough content to clear the 300-byte length gate."""
    return (
        'import { useState } from "react";\n'
        'export default function App() {\n'
        '  const [input, setInput] = useState("");\n'
        '  const pattern = ' + regex_literal + ';\n'
        '  const isValid = pattern.test(input);\n'
        '  return (\n'
        '    <div>\n'
        '      <h1>Regex Validator</h1>\n'
        '      <input value={input} onChange={e => setInput(e.target.value)}/>\n'
        '      <p>Valid: {isValid ? "yes" : "no"}</p>\n'
        '      <p>Current pattern source: {pattern.source}</p>\n'
        '      <p>Padding content for the gate length minimum</p>\n'
        '    </div>\n'
        '  );\n'
        '}\n'
    )


def test_fire121_a_plus_plus_blocks():
    """Fire 121 exact: /^(a+)+$/."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "rv", _padded_app('/^(a+)+$/'))
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "regex validator"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
        assert "ReDoS" in r or "backtracking" in r
        assert "(a+)+" in r


def test_nested_char_class_blocks():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "rv", _padded_app('/^([abc]+)+$/'))
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "regex"
        r = _check_deliverable_complete(str(ws))
        assert r is not None


def test_w_plus_plus_blocks():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "rv", _padded_app(r'/^(\w+)+$/'))
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "regex"
        r = _check_deliverable_complete(str(ws))
        assert r is not None


def test_d_star_star_blocks():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "rv", _padded_app(r'/^(\d*)*$/'))
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "regex"
        r = _check_deliverable_complete(str(ws))
        assert r is not None


def test_dot_plus_plus_blocks():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "rv", _padded_app('/^(.+)+$/'))
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "regex"
        r = _check_deliverable_complete(str(ws))
        assert r is not None


def test_dot_star_star_blocks():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "rv", _padded_app('/^(.*)*$/'))
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "regex"
        r = _check_deliverable_complete(str(ws))
        assert r is not None


def test_safe_email_regex_passes():
    """Regression: normal email / phone regexes must pass."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(
            tmp, "rv",
            _padded_app(r'/^[a-z0-9]+@[a-z]+\.[a-z]+$/'),
        )
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "email validator"
        assert _check_deliverable_complete(str(ws)) is None


def test_safe_phone_regex_passes():
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(
            tmp, "rv",
            _padded_app(r'/^\d{3}-\d{3}-\d{4}$/'),
        )
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "phone validator"
        assert _check_deliverable_complete(str(ws)) is None


def test_non_nested_quantifier_passes():
    """Single `+` or `*` without nesting — totally fine."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "rv", _padded_app(r'/[a-z]+\.com/'))
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "regex"
        assert _check_deliverable_complete(str(ws)) is None


def test_w_star_plus_blocks():
    """`(\\w*)+` — also catastrophic."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = _make(tmp, "rv", _padded_app(r'/^(\w*)+$/'))
        fs_state._session_last_project = "rv"
        fs_state._session_task_prompt = "regex"
        r = _check_deliverable_complete(str(ws))
        assert r is not None
