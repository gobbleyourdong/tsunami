"""Tests for Chunk 1: File-Backed Context Intelligence.

Verifies the complete file-backed context system:
- Lower persistence threshold (500 chars)
- Hash-based .context/ storage with dedup
- file_read smart preview (first 10 + last 5 lines)
- shell_exec smart preview (last 20 lines)
- Compact 1-line references in context
"""

import os
import tempfile
import pytest

from tsunami.tool_result_storage import (
    maybe_persist,
    persist_tool_result,
    generate_file_read_preview,
    generate_shell_exec_preview,
    generate_default_preview,
    _content_hash,
    _count_lines,
    PERSISTENCE_THRESHOLD,
    FILE_READ_HEAD,
    FILE_READ_TAIL,
    SHELL_EXEC_TAIL,
    PREVIEW_MAX_LINES,
)


class TestThreshold:
    """Threshold lowered from 2000 to 500 chars."""

    def test_threshold_is_500(self):
        assert PERSISTENCE_THRESHOLD == 500

    def test_501_chars_persisted(self):
        tmpdir = tempfile.mkdtemp()
        content = "x" * 501
        result = maybe_persist("shell_exec", content, tmpdir)
        assert ".context/" in result

    def test_500_chars_not_persisted(self):
        tmpdir = tempfile.mkdtemp()
        content = "x" * 500
        result = maybe_persist("shell_exec", content, tmpdir)
        assert result == content  # unchanged

    def test_499_chars_not_persisted(self):
        tmpdir = tempfile.mkdtemp()
        content = "x" * 499
        result = maybe_persist("match_grep", content, tmpdir)
        assert result == content


class TestHashStorage:
    """Storage uses .context/ with hash-based filenames."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_stored_in_context_dir(self):
        content = "x" * 1000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        assert result is not None
        assert os.path.join(self.tmpdir, ".context") in result["filepath"]

    def test_hash_deterministic(self):
        assert _content_hash("hello") == _content_hash("hello")

    def test_hash_differs_for_different_content(self):
        assert _content_hash("hello") != _content_hash("world")

    def test_dedup_identical_content(self):
        """Same content -> same file, no duplicates on disk."""
        content = "dedup test\n" * 200
        r1 = persist_tool_result("shell_exec", content, self.tmpdir)
        r2 = persist_tool_result("file_read", content, self.tmpdir)
        assert r1["filepath"] == r2["filepath"]

        # Only one file on disk
        context_dir = os.path.join(self.tmpdir, ".context")
        files = os.listdir(context_dir)
        assert len(files) == 1

    def test_different_content_different_files(self):
        c1 = "content A\n" * 200
        c2 = "content B\n" * 200
        r1 = persist_tool_result("shell_exec", c1, self.tmpdir)
        r2 = persist_tool_result("shell_exec", c2, self.tmpdir)
        assert r1["filepath"] != r2["filepath"]

    def test_relative_path_format(self):
        content = "x" * 1000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        assert result["relative"].startswith(".context/")
        assert result["relative"].endswith(".txt")


class TestFileReadPreviewIntegration:
    """file_read persistence with smart head+tail preview."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_file_read_is_persisted(self):
        """file_read was excluded before — now it's persisted."""
        content = "line\n" * 200
        result = persist_tool_result("file_read", content, self.tmpdir)
        assert result is not None

    def test_preview_has_head_and_tail(self):
        lines = [f"import {i}\n" for i in range(100)]
        content = "".join(lines)
        result = maybe_persist("file_read", content, self.tmpdir)
        # Head lines
        assert "import 0" in result
        assert "import 9" in result
        # Tail lines
        assert "import 99" in result
        assert "import 95" in result
        # Middle omitted
        assert "import 50" not in result

    def test_small_file_not_persisted(self):
        content = "short file"
        result = maybe_persist("file_read", content, self.tmpdir)
        assert result == content

    def test_reference_line_present(self):
        content = "x\n" * 300
        result = maybe_persist("file_read", content, self.tmpdir)
        first_line = result.split("\n")[0]
        assert "lines" in first_line
        assert ".context/" in first_line


class TestShellExecPreviewIntegration:
    """shell_exec persistence with tail-only preview."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_tail_only_in_context(self):
        lines = [f"step {i}: processing\n" for i in range(100)]
        content = "".join(lines)
        result = maybe_persist("shell_exec", content, self.tmpdir)
        # Last 20 lines present
        assert "step 99" in result
        assert "step 80" in result
        # Early lines gone
        assert "step 0" not in result
        assert "step 10" not in result

    def test_full_content_on_disk(self):
        lines = [f"line {i}\n" for i in range(100)]
        content = "".join(lines)
        persist_result = persist_tool_result("shell_exec", content, self.tmpdir)
        saved = open(persist_result["filepath"]).read()
        assert saved == content
        assert "line 0" in saved
        assert "line 99" in saved


class TestContextSavings:
    """Verify the context savings are real."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_large_file_read_compressed(self):
        """A 1000-line file should produce << 1000 lines in context."""
        lines = [f"const x{i} = {i};\n" for i in range(1000)]
        content = "".join(lines)
        result = maybe_persist("file_read", content, self.tmpdir)
        # Original: 1000 lines. Context: ~15 lines + 1 reference + 1 separator
        result_lines = result.count("\n")
        assert result_lines < 25  # massive savings
        assert len(result) < len(content) / 5  # at least 5x compression

    def test_large_shell_output_compressed(self):
        """npm install output (500 lines) should keep only tail."""
        lines = [f"npm WARN deprecated package{i}@1.0.0\n" for i in range(500)]
        content = "".join(lines)
        result = maybe_persist("shell_exec", content, self.tmpdir)
        result_lines = result.count("\n")
        assert result_lines < 30
        assert len(result) < len(content) / 5

    def test_moderate_content_near_threshold(self):
        """Content just over threshold still gets persisted."""
        content = "x" * 501
        result = maybe_persist("match_grep", content, self.tmpdir)
        assert ".context/" in result


class TestLineCount:
    """_count_lines utility."""

    def test_empty(self):
        assert _count_lines("") == 0

    def test_one_line_no_newline(self):
        assert _count_lines("hello") == 1

    def test_one_line_with_newline(self):
        assert _count_lines("hello\n") == 1

    def test_multiple_lines(self):
        assert _count_lines("a\nb\nc\n") == 3

    def test_trailing_no_newline(self):
        assert _count_lines("a\nb\nc") == 3
