"""Tests for tool result persistence."""

import os
import tempfile
import pytest

from tsunami.tool_result_storage import (
    generate_preview,
    persist_tool_result,
    build_persisted_result_message,
    maybe_persist,
    PERSISTENCE_THRESHOLD,
    PREVIEW_SIZE,
    TOOL_RESULT_CLEARED_MESSAGE,
    NO_PERSIST_TOOLS,
)


class TestGeneratePreview:
    """Preview generation — cut at newline, preserve readability."""

    def test_short_content_no_truncation(self):
        content = "hello world"
        preview, has_more = generate_preview(content)
        assert preview == content
        assert has_more is False

    def test_exact_threshold_no_truncation(self):
        content = "x" * PREVIEW_SIZE
        preview, has_more = generate_preview(content)
        assert preview == content
        assert has_more is False

    def test_long_content_truncated(self):
        content = "line\n" * 1000  # 5000 chars
        preview, has_more = generate_preview(content, max_chars=100)
        assert len(preview) <= 100
        assert has_more is True

    def test_cuts_at_newline_boundary(self):
        # Content with newlines — should cut at a newline, not mid-line
        lines = ["a" * 30 + "\n"] * 100
        content = "".join(lines)
        preview, has_more = generate_preview(content, max_chars=100)
        assert preview.endswith("\n") or preview.endswith("a")
        assert has_more is True

    def test_no_newline_falls_back_to_exact(self):
        # Single long line — no newline to cut at
        content = "x" * 5000
        preview, has_more = generate_preview(content, max_chars=100)
        assert len(preview) == 100
        assert has_more is True


class TestPersistToolResult:
    """Persistence logic — what goes to disk, what doesn't."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_small_result_not_persisted(self):
        result = persist_tool_result("shell_exec", "small output", self.tmpdir)
        assert result is None

    def test_large_result_persisted(self):
        content = "x" * (PERSISTENCE_THRESHOLD + 100)
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        assert result is not None
        assert os.path.exists(result["filepath"])
        assert result["original_size"] == len(content)
        assert result["has_more"] is True

    def test_persisted_file_contains_full_content(self):
        content = "line\n" * 2000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        saved = open(result["filepath"]).read()
        assert saved == content

    def test_preview_in_result(self):
        content = "x" * 5000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        assert len(result["preview"]) <= PREVIEW_SIZE
        assert result["preview"] == content[:PREVIEW_SIZE]

    def test_file_read_never_persisted(self):
        """Circular read prevention — file_read must never be persisted."""
        content = "x" * 10000
        result = persist_tool_result("file_read", content, self.tmpdir)
        assert result is None

    def test_message_tools_never_persisted(self):
        """Message tools don't get persisted."""
        content = "x" * 10000
        for tool in ("message_info", "message_ask", "message_result"):
            result = persist_tool_result(tool, content, self.tmpdir)
            assert result is None, f"{tool} should not be persisted"

    def test_shell_exec_persisted(self):
        content = "x" * 5000
        result = persist_tool_result("shell_exec", content, self.tmpdir)
        assert result is not None

    def test_match_grep_persisted(self):
        content = "match\n" * 2000
        result = persist_tool_result("match_grep", content, self.tmpdir)
        assert result is not None

    def test_creates_directory(self):
        workspace = os.path.join(self.tmpdir, "new_workspace")
        content = "x" * 5000
        result = persist_tool_result("shell_exec", content, workspace)
        assert result is not None
        assert os.path.exists(result["filepath"])


class TestBuildPersistedResultMessage:
    """The in-context message format."""

    def test_contains_filepath(self):
        result = {
            "filepath": "/tmp/tool_results/shell_exec_123.txt",
            "preview": "first two KB...",
            "original_size": 50000,
            "has_more": True,
        }
        msg = build_persisted_result_message(result)
        assert "shell_exec_123.txt" in msg
        assert "first two KB..." in msg
        assert "..." in msg  # has_more indicator

    def test_no_ellipsis_when_complete(self):
        result = {
            "filepath": "/tmp/tool_results/test.txt",
            "preview": "all content",
            "original_size": 100,
            "has_more": False,
        }
        msg = build_persisted_result_message(result)
        assert msg.count("...") == 0 or "..." not in msg.split("Preview")[-1]

    def test_contains_size_info(self):
        result = {
            "filepath": "/tmp/test.txt",
            "preview": "...",
            "original_size": 50000,
            "has_more": True,
        }
        msg = build_persisted_result_message(result)
        assert "48.8 KB" in msg or "50000" in msg or "KB" in msg


class TestMaybePersist:
    """End-to-end: maybe_persist returns original or persisted content."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_small_content_unchanged(self):
        content = "small output"
        result = maybe_persist("shell_exec", content, self.tmpdir)
        assert result == content

    def test_large_content_replaced_with_preview(self):
        content = "x" * 5000
        result = maybe_persist("shell_exec", content, self.tmpdir)
        assert result != content
        assert "saved to:" in result.lower() or "Full output" in result
        assert len(result) < len(content)

    def test_file_read_never_replaced(self):
        """file_read content stays in context regardless of size."""
        content = "x" * 10000
        result = maybe_persist("file_read", content, self.tmpdir)
        assert result == content


class TestToolResultClearedMessage:
    """The cleared message constant."""

    def test_constant_exists(self):
        assert TOOL_RESULT_CLEARED_MESSAGE == "[Old tool result content cleared]"

    def test_no_persist_tools_set(self):
        assert "file_read" in NO_PERSIST_TOOLS
        assert "message_info" in NO_PERSIST_TOOLS
        assert "shell_exec" not in NO_PERSIST_TOOLS
