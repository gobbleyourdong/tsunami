"""Tests for edit context extraction — smart snippet loading."""

import os
import tempfile
import pytest

from tsunami.edit_context import (
    find_in_file,
    get_edit_preview,
    count_matches,
    _fuzzy_find,
    DEFAULT_CONTEXT_LINES,
)


class TestFindInFile:
    """Locate text in files with surrounding context."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write_file(self, name: str, content: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_exact_match(self):
        content = "line 1\nline 2\ntarget line\nline 4\nline 5"
        path = self._write_file("test.py", content)
        result = find_in_file(path, "target line")
        assert result is not None
        assert result["match_line"] == 2
        assert result["match_text"] == "target line"

    def test_context_lines(self):
        content = "\n".join(f"line {i}" for i in range(10))
        path = self._write_file("test.py", content)
        result = find_in_file(path, "line 5", context_lines=2)
        assert result is not None
        assert len(result["before"]) == 2
        assert len(result["after"]) == 2
        assert "line 3" in result["before"]
        assert "line 4" in result["before"]
        assert "line 6" in result["after"]
        assert "line 7" in result["after"]

    def test_multiline_needle(self):
        content = "a\nb\nc\nd\ne"
        path = self._write_file("test.py", content)
        result = find_in_file(path, "b\nc\nd")
        assert result is not None
        assert result["match_line"] == 1
        assert result["match_end_line"] == 3

    def test_not_found(self):
        path = self._write_file("test.py", "hello world")
        result = find_in_file(path, "nonexistent")
        assert result is None

    def test_nonexistent_file(self):
        result = find_in_file("/nonexistent/file.py", "test")
        assert result is None

    def test_match_at_start(self):
        content = "first line\nsecond line\nthird line"
        path = self._write_file("test.py", content)
        result = find_in_file(path, "first line")
        assert result is not None
        assert result["match_line"] == 0
        assert result["before"] == []

    def test_match_at_end(self):
        content = "first\nsecond\nlast"
        path = self._write_file("test.py", content)
        result = find_in_file(path, "last")
        assert result is not None
        assert result["after"] == []

    def test_total_lines(self):
        content = "\n".join(f"line {i}" for i in range(50))
        path = self._write_file("test.py", content)
        result = find_in_file(path, "line 25")
        assert result["total_lines"] == 50

    def test_whitespace_fuzzy_match(self):
        content = "def foo():  \n    pass  \n"
        path = self._write_file("test.py", content)
        # Search without trailing whitespace
        result = find_in_file(path, "def foo():\n    pass")
        assert result is not None


class TestFuzzyFind:
    """Whitespace-normalized matching."""

    def test_trailing_whitespace(self):
        content = "hello  \nworld  \n"
        needle = "hello\nworld"
        idx = _fuzzy_find(content, needle)
        assert idx >= 0

    def test_no_match(self):
        idx = _fuzzy_find("hello world", "goodbye")
        assert idx == -1

    def test_exact_still_works(self):
        idx = _fuzzy_find("hello world", "hello")
        assert idx == 0


class TestCountMatches:
    """Ambiguity detection before editing."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_single_match(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("unique text here\nother stuff")
        assert count_matches(path, "unique text") == 1

    def test_multiple_matches(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("import os\nimport os\nimport os\n")
        assert count_matches(path, "import os") == 3

    def test_no_matches(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("hello world")
        assert count_matches(path, "nonexistent") == 0

    def test_nonexistent_file(self):
        assert count_matches("/nonexistent", "test") == 0


class TestGetEditPreview:
    """Preview of what an edit would look like."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_simple_preview(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("line 1\nold text\nline 3\n")
        preview = get_edit_preview(path, "old text", "new text")
        assert preview is not None
        assert "- " in preview  # old text marked with -
        assert "+ " in preview  # new text marked with +
        assert "old text" in preview
        assert "new text" in preview

    def test_preview_not_found(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("hello")
        preview = get_edit_preview(path, "nonexistent", "replacement")
        assert preview is None

    def test_preview_has_context(self):
        path = os.path.join(self.tmpdir, "test.py")
        content = "\n".join(f"line {i}" for i in range(10))
        with open(path, "w") as f:
            f.write(content)
        preview = get_edit_preview(path, "line 5", "modified 5", context_lines=2)
        assert "line 3" in preview  # before context
        assert "line 4" in preview
        assert "line 6" in preview  # after context
        assert "line 7" in preview
