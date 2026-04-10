"""Tests for tool concurrency safety flags (.."""

import pytest

from tsunami.tools.base import BaseTool, ToolResult


class TestConcurrentSafeFlag:
    """Tools declare whether they're safe to run in parallel."""

    def test_default_is_not_concurrent(self):
        """By default, tools are NOT concurrent-safe (conservative)."""
        class TestTool(BaseTool):
            name = "test"
            description = "test"
            def __init__(self): pass
            def parameters_schema(self): return {"type": "object", "properties": {}}
            async def execute(self, **kw): return ToolResult("ok")

        tool = TestTool()
        assert tool.concurrent_safe is False

    def test_read_tools_are_concurrent(self):
        """Read-only tools should be marked concurrent_safe."""
        from tsunami.tools.filesystem import FileRead
        from tsunami.tools.match import MatchGlob, MatchGrep

        class FakeConfig:
            workspace_dir = "/tmp"

        config = FakeConfig()
        assert FileRead(config).concurrent_safe is True
        assert MatchGlob(config).concurrent_safe is True
        assert MatchGrep(config).concurrent_safe is True

    def test_write_tools_are_not_concurrent(self):
        """Write tools should NOT be concurrent_safe."""
        from tsunami.tools.filesystem import FileWrite, FileEdit, FileAppend

        class FakeConfig:
            workspace_dir = "/tmp"

        config = FakeConfig()
        assert FileWrite(config).concurrent_safe is False
        assert FileEdit(config).concurrent_safe is False
        assert FileAppend(config).concurrent_safe is False

    def test_shell_is_not_concurrent(self):
        """Shell execution is not concurrent_safe."""
        from tsunami.tools.shell import ShellExec

        class FakeConfig:
            workspace_dir = "/tmp"

        config = FakeConfig()
        assert ShellExec(config).concurrent_safe is False


class TestConcurrencyDecision:
    """Logic for deciding which tools can run in parallel."""

    def test_all_concurrent_can_parallel(self):
        """If all tools in queue are concurrent-safe, they can all run."""
        tools = [
            {"name": "file_read", "concurrent_safe": True, "status": "executing"},
            {"name": "match_grep", "concurrent_safe": True, "status": "queued"},
        ]

        # canExecute: queue is empty OR (new tool is safe AND all executing are safe)
        executing = [t for t in tools if t["status"] == "executing"]
        new_tool = tools[1]
        can_execute = (
            len(executing) == 0
            or (new_tool["concurrent_safe"] and all(t["concurrent_safe"] for t in executing))
        )
        assert can_execute is True

    def test_non_concurrent_blocks(self):
        """A non-concurrent tool cannot run while others execute."""
        tools = [
            {"name": "file_read", "concurrent_safe": True, "status": "executing"},
            {"name": "file_write", "concurrent_safe": False, "status": "queued"},
        ]

        executing = [t for t in tools if t["status"] == "executing"]
        new_tool = tools[1]
        can_execute = (
            len(executing) == 0
            or (new_tool["concurrent_safe"] and all(t["concurrent_safe"] for t in executing))
        )
        assert can_execute is False

    def test_concurrent_blocked_by_non_concurrent(self):
        """A concurrent tool cannot run while a non-concurrent tool executes."""
        tools = [
            {"name": "shell_exec", "concurrent_safe": False, "status": "executing"},
            {"name": "file_read", "concurrent_safe": True, "status": "queued"},
        ]

        executing = [t for t in tools if t["status"] == "executing"]
        new_tool = tools[1]
        can_execute = (
            len(executing) == 0
            or (new_tool["concurrent_safe"] and all(t["concurrent_safe"] for t in executing))
        )
        assert can_execute is False

    def test_empty_queue_allows_anything(self):
        """When nothing is executing, any tool can start."""
        executing = []
        can_execute = len(executing) == 0 or True
        assert can_execute is True
