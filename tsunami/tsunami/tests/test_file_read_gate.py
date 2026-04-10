"""Tests for file read size gate ("""

import os
import tempfile
import asyncio
import pytest

from tsunami.tools.filesystem import FileRead, MAX_FILE_SIZE_BYTES


class FakeConfig:
    """Minimal config for testing."""
    def __init__(self, workspace_dir):
        self.workspace_dir = workspace_dir


def run(coro):
    """Helper to run async tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestFileReadSizeGate:
    """Pre-read size gate rejects huge files without offset/limit."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = FakeConfig(self.tmpdir)
        self.tool = FileRead(self.config)

    def _write_file(self, name: str, size_bytes: int) -> str:
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write("x" * size_bytes)
        return path

    def test_small_file_reads_normally(self):
        path = self._write_file("small.txt", 1000)
        result = run(self.tool.execute(path=path))
        assert not result.is_error
        assert "small.txt" in result.content

    def test_large_file_rejected_without_limit(self):
        """Files > 256KB rejected when no offset/limit specified."""
        path = self._write_file("huge.txt", MAX_FILE_SIZE_BYTES + 1000)
        result = run(self.tool.execute(path=path))
        assert result.is_error
        assert "too large" in result.content.lower()
        assert "offset" in result.content.lower()

    def test_large_file_allowed_with_explicit_limit(self):
        """Large files are readable when limit is explicitly set (< 500)."""
        path = self._write_file("huge.txt", MAX_FILE_SIZE_BYTES + 1000)
        result = run(self.tool.execute(path=path, offset=0, limit=50))
        assert not result.is_error

    def test_large_file_allowed_with_offset(self):
        """Large files are readable when offset is non-zero."""
        # Write a file with actual lines
        path = os.path.join(self.tmpdir, "big_lines.txt")
        with open(path, "w") as f:
            for i in range(50000):
                f.write(f"line {i}\n")
        result = run(self.tool.execute(path=path, offset=100, limit=50))
        assert not result.is_error

    def test_error_message_has_pagination_examples(self):
        """Error message includes copy-pasteable pagination examples."""
        path = self._write_file("huge.txt", MAX_FILE_SIZE_BYTES + 1000)
        result = run(self.tool.execute(path=path))
        assert "file_read" in result.content
        assert "offset=0" in result.content
        assert "limit=100" in result.content

    def test_exact_threshold_passes(self):
        """File exactly at threshold should pass."""
        path = self._write_file("borderline.txt", MAX_FILE_SIZE_BYTES)
        result = run(self.tool.execute(path=path))
        assert not result.is_error

    def test_file_not_found(self):
        result = run(self.tool.execute(path="/nonexistent/file.txt"))
        assert result.is_error
        assert "not found" in result.content.lower()

    def test_truncation_still_works(self):
        """Files within size gate but with many lines still get char-truncated."""
        path = os.path.join(self.tmpdir, "many_lines.txt")
        with open(path, "w") as f:
            for i in range(5000):
                f.write(f"line {i}: {'x' * 50}\n")
        # This is > 256KB but we'll request a specific range
        result = run(self.tool.execute(path=path, offset=0, limit=200))
        assert not result.is_error
        # Should have content (may be truncated by char limit)
        assert "line 0" in result.content


class TestFileReadSizeGateEdgeCases:
    """Edge cases for the size gate."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = FakeConfig(self.tmpdir)
        self.tool = FileRead(self.config)

    def test_empty_file(self):
        path = os.path.join(self.tmpdir, "empty.txt")
        with open(path, "w") as f:
            pass
        result = run(self.tool.execute(path=path))
        assert not result.is_error

    def test_binary_like_content(self):
        """File with unusual characters should still work."""
        path = os.path.join(self.tmpdir, "binary.txt")
        with open(path, "wb") as f:
            f.write(b"\x00\x01\x02" * 100)
        result = run(self.tool.execute(path=path))
        assert not result.is_error
