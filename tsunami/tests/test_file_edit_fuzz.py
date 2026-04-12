"""FileEdit fuzzy-match fallbacks.

QA-3 Test 32: the agent's placeholder-fix recovery loop silently failed
because file_edit's exact-match didn't know how to handle the model
emitting unindented old_text against 10-space-indented on-disk content.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from tsunami.config import TsunamiConfig
from tsunami.tools.filesystem import FileEdit


def _make_tool(workspace: str) -> FileEdit:
    cfg = TsunamiConfig(
        model_backend="api",
        model_name="test",
        model_endpoint="http://localhost:9999",
        workspace_dir=workspace,
    )
    return FileEdit(cfg)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_indent_normalized_match_10_space():
    """QA-3 Test 32 exact repro: 10-space-indented JSX, model emits column-0 old_text."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "App.tsx"
        target.write_text(
            "export default function App() {\n"
            "  return (\n"
            "    <div>\n"
            "      <div className=\"flex\">\n"
            "        <div>\n"
            "          {/* Placeholder for the button */}\n"
            "          <div className=\"h-12 w-32 bg-bg-3 rounded animate-pulse\"></div>\n"
            "        </div>\n"
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )
        tool = _make_tool(tmp)
        old_text = (
            "{/* Placeholder for the button */}\n"
            "<div className=\"h-12 w-32 bg-bg-3 rounded animate-pulse\"></div>"
        )
        new_text = "<button onClick={() => alert('hi')}>Hello</button>"
        result = _run(tool.execute(path=str(target), old_text=old_text, new_text=new_text))
        assert not result.is_error, f"expected fuzzy match, got error: {result.content}"
        assert "indent-normalized" in result.content
        # Verify the replacement preserved the 10-space indent
        after = target.read_text()
        assert "          <button onClick={() => alert('hi')}>Hello</button>" in after
        assert "Placeholder for the button" not in after
        assert "animate-pulse" not in after


def test_indent_normalized_match_single_line():
    """Single-line old_text with indent mismatch also works."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "App.tsx"
        target.write_text(
            "function App() {\n"
            "    const placeholder = 'loading'\n"
            "    return <div>{placeholder}</div>\n"
            "}\n"
        )
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path=str(target),
            old_text="const placeholder = 'loading'",
            new_text="const [count, setCount] = useState(0)",
        ))
        assert not result.is_error
        after = target.read_text()
        assert "    const [count, setCount] = useState(0)" in after


def test_indent_normalized_multiline_new_text_reindented():
    """new_text with multiple lines gets the same indent applied to each."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "App.tsx"
        target.write_text(
            "return (\n"
            "      <div>\n"
            "      <p>old</p>\n"
            "      </div>\n"
            ")\n"
        )
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path=str(target),
            old_text="<div>\n<p>old</p>\n</div>",
            new_text="<div>\n<p>new line 1</p>\n<p>new line 2</p>\n</div>",
        ))
        assert not result.is_error
        after = target.read_text()
        assert "      <p>new line 1</p>" in after
        assert "      <p>new line 2</p>" in after


def test_indent_match_refuses_inconsistent_indent():
    """Window with mismatched indents across lines should NOT match."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "file.txt"
        # Lines A and B are at different indents — inconsistent window
        target.write_text("  alpha\n    beta\n  gamma\n")
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path=str(target),
            old_text="alpha\nbeta",
            new_text="X\nY",
        ))
        # Should fall through to "Text not found" — inconsistent indent window rejected
        assert result.is_error
        assert "not found" in result.content.lower()


def test_exact_match_unaffected():
    """The exact-match happy path still works without touching the fuzzy code."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "file.txt"
        target.write_text("hello world\ngoodbye moon\n")
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path=str(target),
            old_text="hello world",
            new_text="hi there",
        ))
        assert not result.is_error
        assert "indent-normalized" not in result.content  # used exact path
        after = target.read_text()
        assert after == "hi there\ngoodbye moon\n"


def test_ambiguous_indent_match_refused():
    """If the indent-stripped pattern appears twice, don't guess — refuse."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "file.txt"
        target.write_text(
            "  line one\n"
            "  line two\n"
            "    line one\n"
            "    line two\n"
        )
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path=str(target),
            old_text="line one\nline two",
            new_text="NEW",
        ))
        assert result.is_error
        assert "not found" in result.content.lower()
