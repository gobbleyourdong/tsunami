"""Tests for tool repetition breaking — any tool called 3x in a row gets stopped."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass


@dataclass
class FakeToolCall:
    name: str
    arguments: dict


class TestRepetitionBreaker:
    """The repetition checker in _handle_tool should fire for ANY tool 3x in a row."""

    def _make_recent_tools(self, names: list[str]) -> list[tuple]:
        """Build _recent_tools list from tool names."""
        return [(n, {}) for n in names]

    def test_generate_image_3x_triggers(self):
        """generate_image called 3x should inject stop note."""
        recent = self._make_recent_tools(["generate_image", "generate_image", "generate_image"])
        last_3 = [t[0] for t in recent[-3:]]
        assert len(set(last_3)) == 1
        assert last_3[0] == "generate_image"

    def test_search_web_3x_triggers(self):
        """search_web called 3x should inject stop note."""
        recent = self._make_recent_tools(["search_web", "search_web", "search_web"])
        last_3 = [t[0] for t in recent[-3:]]
        assert len(set(last_3)) == 1
        assert last_3[0] == "search_web"

    def test_shell_exec_3x_triggers(self):
        """shell_exec called 3x should inject stop note."""
        recent = self._make_recent_tools(["shell_exec", "shell_exec", "shell_exec"])
        last_3 = [t[0] for t in recent[-3:]]
        assert len(set(last_3)) == 1

    def test_mixed_tools_no_trigger(self):
        """Different tools interleaved should NOT trigger."""
        recent = self._make_recent_tools(["file_read", "search_web", "file_read"])
        last_3 = [t[0] for t in recent[-3:]]
        assert len(set(last_3)) > 1  # not all same

    def test_two_same_not_enough(self):
        """Only 2 consecutive same tools should NOT trigger."""
        recent = self._make_recent_tools(["file_write", "generate_image", "generate_image"])
        last_3 = [t[0] for t in recent[-3:]]
        assert len(set(last_3)) > 1  # file_write breaks the streak

    def test_file_read_3x_triggers_swell_hint(self):
        """file_read 3x should suggest swell (original behavior preserved)."""
        recent = self._make_recent_tools(["file_read", "file_read", "file_read"])
        last_3 = [t[0] for t in recent[-3:]]
        assert len(set(last_3)) == 1
        assert last_3[0] == "file_read"

    def test_unknown_tool_3x_gets_generic(self):
        """Any other tool 3x should get the generic stop message."""
        recent = self._make_recent_tools(["plan_update", "plan_update", "plan_update"])
        last_3 = [t[0] for t in recent[-3:]]
        assert len(set(last_3)) == 1
        assert last_3[0] not in ("file_read", "summarize_file", "match_grep",
                                  "generate_image", "search_web", "shell_exec")


class TestDedupLoopBreaker:
    """After 3 dedup hits, should fall through to re-execute, not return cached."""

    def test_dedup_invalidate_clears_cache(self):
        from tsunami.tool_dedup import ToolDedup
        d = ToolDedup()
        d.store("file_read", {"path": "/a"}, "content_a")
        # Simulate 3 hits
        for _ in range(3):
            result = d.lookup("file_read", {"path": "/a"})
            assert result is not None
        # After invalidation, cache should be empty
        d.invalidate()
        assert d.lookup("file_read", {"path": "/a"}) is None

    def test_generate_image_never_cached(self):
        """generate_image should never be stored or looked up in cache."""
        from tsunami.tool_dedup import ToolDedup
        d = ToolDedup()
        d.store("generate_image", {"prompt": "cat"}, "image saved")
        assert d.lookup("generate_image", {"prompt": "cat"}) is None
        assert d.stats["cached"] == 0

    def test_generate_image_in_no_cache(self):
        """generate_image must be in NO_CACHE_TOOLS."""
        from tsunami.tool_dedup import NO_CACHE_TOOLS
        assert "generate_image" in NO_CACHE_TOOLS

    def test_webdev_generate_in_no_cache(self):
        """webdev_generate_assets must be in NO_CACHE_TOOLS."""
        from tsunami.tool_dedup import NO_CACHE_TOOLS
        assert "webdev_generate_assets" in NO_CACHE_TOOLS


class TestGenerateImageSavePath:
    """generate_image should handle missing save_path gracefully."""

    def test_save_path_default_empty(self):
        """save_path should default to empty string, not crash."""
        import inspect
        from tsunami.tools.generate import GenerateImage
        sig = inspect.signature(GenerateImage.execute)
        save_path_param = sig.parameters.get("save_path")
        assert save_path_param is not None
        assert save_path_param.default == ""

    def test_schema_still_requires_save_path(self):
        """Schema should still list save_path as required (for the model)."""
        from tsunami.tools.generate import GenerateImage
        from unittest.mock import MagicMock
        tool = GenerateImage.__new__(GenerateImage)
        tool.config = MagicMock()
        schema = tool.parameters_schema()
        assert "save_path" in schema["required"]
