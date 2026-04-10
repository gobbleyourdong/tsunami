"""Tests for tool result persistence."""

import os
import tempfile
import pytest

from tsunami.tool_result_storage import (
    generate_preview,
    generate_file_read_preview,
    generate_shell_exec_preview,
    generate_default_preview,
    persist_tool_result,
    build_persisted_result_message,
    maybe_persist,
    PERSISTENCE_THRESHOLD,
    TOOL_RESULT_CLEARED_MESSAGE,
    NO_PERSIST_TOOLS,
    FILE_READ_HEAD,
    FILE_READ_TAIL,
    SHELL_EXEC_TAIL,
)


class TestGeneratePreview:
    """Preview generation dispatches by tool type."""

    def test_short_content_no_truncation(self):
        content = "hello world"
        preview = generate_preview(content)
        assert preview == content

    def test_file_read_dispatches_correctly(self):
        lines = [f"line {i}\n" for i in range(50)]
        content = "".join(lines)
        preview = generate_preview(content, tool_name="file_read")
        assert "line 0" in preview
        assert "line 49" in preview
        assert "omitted" in preview

    def test_shell_exec_dispatches_correctly(self):
        lines = [f"output {i}\n" for i in range(50)]
        content = "".join(lines)
        preview = generate_preview(content, tool_name="shell_exec")
        assert "output 49" in preview
        assert "output 0" not in preview
        assert "omitted" in preview

    def test_default_dispatches_for_unknown_tool(self):
        lines = [f"line {i}\n" for i in range(50)]
        content = "".join(lines)
        preview = generate_preview(content, tool_name="match_grep")
        assert "line 0" in preview
        assert "omitted" in preview


class TestFileReadPreview:
    """file_read: first 10 + last 5 lines."""

    def test_small_file_kept_whole(self):
        content = "a\nb\nc\n"
        assert generate_file_read_preview(content) == content

    def test_exactly_threshold_kept_whole(self):
        lines = [f"L{i}\n" for i in range(FILE_READ_HEAD + FILE_READ_TAIL)]
        content = "".join(lines)
        assert generate_file_read_preview(content) == content

    def test_large_file_head_and_tail(self):
        lines = [f"line_{i}\n" for i in range(100)]
        content = "".join(lines)
        preview = generate_file_read_preview(content)
        # First 10 lines present
        for i in range(FILE_READ_HEAD):
            assert f"line_{i}\n" in preview
        # Last 5 lines present
        for i in range(100 - FILE_READ_TAIL, 100):
            assert f"line_{i}\n" in preview
        # Middle lines omitted
        assert "line_50" not in preview
        assert "omitted" in preview

    def test_skipped_count_correct(self):
        lines = [f"L{i}\n" for i in range(100)]
        content = "".join(lines)
        preview = generate_file_read_preview(content)
        expected_skipped = 100 - FILE_READ_HEAD - FILE_READ_TAIL
        assert f"{expected_skipped} lines omitted" in preview


class TestShellExecPreview:
    """shell_exec: last 20 lines."""

    def test_small_output_kept_whole(self):
        content = "ok\ndone\n"
        assert generate_shell_exec_preview(content) == content

    def test_large_output_tail_only(self):
        lines = [f"out_{i}\n" for i in range(100)]
        content = "".join(lines)
        preview = generate_shell_exec_preview(content)
        # Last 20 lines present
        for i in range(100 - SHELL_EXEC_TAIL, 100):
            assert f"out_{i}\n" in preview
        # Early lines gone
        assert "out_0" not in preview
        assert "out_10" not in preview

    def test_skipped_count_correct(self):
        lines = [f"L{i}\n" for i in range(50)]
        content = "".join(lines)
        preview = generate_shell_exec_preview(content)
        expected_skipped = 50 - SHELL_EXEC_TAIL
        assert f"{expected_skipped} lines omitted" in preview


class TestPersistToolResult:
    """Persistence logic — what goes to disk, what doesn't."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_small_result_not_persisted(self):
        result = persist_tool_result("shell_exec", "small output", self.tmpdir)
        assert result is None

    def test_large_result_persisted(self):
        content = "x\n" * (PERSISTENCE_THRESHOLD + 100)
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        assert result is not None
        assert os.path.exists(result["filepath"])
        assert result["original_size"] == len(content)
        assert result["line_count"] > 0

    def test_persisted_file_contains_full_content(self):
        content = "line\n" * 2000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        saved = open(result["filepath"]).read()
        assert saved == content

    def test_hash_based_filename(self):
        content = "x" * 1000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        # Filename should be a hash, not a timestamp
        filename = os.path.basename(result["filepath"])
        assert filename.endswith(".txt")
        assert len(filename) == 16  # 12 hex chars + .txt

    def test_dedup_same_content(self):
        """Identical content produces the same file (hash dedup)."""
        content = "identical\n" * 500
        r1 = persist_tool_result("shell_exec", content, self.tmpdir)
        r2 = persist_tool_result("shell_exec", content, self.tmpdir)
        assert r1["filepath"] == r2["filepath"]

    def test_storage_in_context_dir(self):
        content = "x" * 1000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        assert "/.context/" in result["filepath"]
        assert result["relative"].startswith(".context/")

    def test_file_read_now_persisted(self):
        """file_read IS persisted (no longer in NO_PERSIST_TOOLS)."""
        content = "x\n" * 500
        result = persist_tool_result("file_read", content, self.tmpdir)
        assert result is not None

    def test_message_tools_never_persisted(self):
        """Message tools don't get persisted."""
        content = "x" * 10000
        for tool in ("message_info", "message_ask", "message_result"):
            result = persist_tool_result(tool, content, self.tmpdir)
            assert result is None, f"{tool} should not be persisted"

    def test_shell_exec_persisted(self):
        content = "x" * 1000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        assert result is not None

    def test_match_grep_persisted(self):
        content = "match\n" * 500
        result = persist_tool_result("match_grep", content, self.tmpdir)
        assert result is not None

    def test_creates_directory(self):
        workspace = os.path.join(self.tmpdir, "new_workspace")
        content = "x" * 1000
        result = persist_tool_result("shell_exec", content, workspace)
        assert result is not None
        assert os.path.exists(result["filepath"])


class TestBuildPersistedResultMessage:
    """The compact in-context message format."""

    def test_contains_relative_path(self):
        result = {
            "filepath": "/tmp/.context/abc123def456.txt",
            "relative": ".context/abc123def456.txt",
            "preview": "last lines...",
            "line_count": 200,
            "original_size": 50000,
        }
        msg = build_persisted_result_message("shell_exec", result)
        assert ".context/abc123def456.txt" in msg

    def test_contains_line_count(self):
        result = {
            "filepath": "/tmp/.context/abc.txt",
            "relative": ".context/abc.txt",
            "preview": "preview",
            "line_count": 42,
            "original_size": 2000,
        }
        msg = build_persisted_result_message("shell_exec", result)
        assert "42 lines" in msg

    def test_compact_format(self):
        """First line should be a compact reference, then preview."""
        result = {
            "filepath": "/tmp/.context/abc.txt",
            "relative": ".context/abc.txt",
            "preview": "the preview content",
            "line_count": 100,
            "original_size": 5000,
        }
        msg = build_persisted_result_message("shell_exec", result)
        lines = msg.split("\n")
        # First line is the reference
        assert lines[0].startswith("[")
        assert ".context/" in lines[0]
        # Preview follows
        assert "the preview content" in msg


class TestMaybePersist:
    """End-to-end: maybe_persist returns original or persisted content."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_small_content_unchanged(self):
        content = "small output"
        result = maybe_persist("shell_exec", content, self.tmpdir)
        assert result == content

    def test_large_content_replaced_with_reference(self):
        content = "x\n" * 500
        result = maybe_persist("shell_exec", content, self.tmpdir)
        assert result != content
        assert ".context/" in result
        assert len(result) < len(content)

    def test_file_read_now_persisted(self):
        """file_read content gets persisted with smart preview."""
        lines = [f"line {i}\n" for i in range(100)]
        content = "".join(lines)
        result = maybe_persist("file_read", content, self.tmpdir)
        assert ".context/" in result
        assert "line 0" in result  # head preserved
        assert "line 99" in result  # tail preserved

    def test_shell_exec_tail_preview(self):
        """shell_exec content gets persisted with tail preview."""
        lines = [f"out {i}\n" for i in range(100)]
        content = "".join(lines)
        result = maybe_persist("shell_exec", content, self.tmpdir)
        assert ".context/" in result
        assert "out 99" in result  # tail preserved
        assert "out 0" not in result  # head dropped


class TestToolResultClearedMessage:
    """The cleared message constant."""

    def test_constant_exists(self):
        assert TOOL_RESULT_CLEARED_MESSAGE == "[Old tool result content cleared]"

    def test_no_persist_tools_set(self):
        assert "file_read" not in NO_PERSIST_TOOLS  # file_read now persisted
        assert "message_info" in NO_PERSIST_TOOLS
        assert "shell_exec" not in NO_PERSIST_TOOLS
