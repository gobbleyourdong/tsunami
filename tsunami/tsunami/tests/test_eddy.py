"""Tests for eddy worker agent — tool execution and result formatting."""

import asyncio
import os
import tempfile
import pytest

from tsunami.eddy import (
    _execute_bee_tool,
    BeeResult,
    EDDY_TOOLS,
    format_swarm_results,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestBeeToolExecution:
    """Eddies can execute tools locally."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "test.py"), "w") as f:
            f.write("def hello():\n    return 'world'\n\nprint(hello())\n")

    def test_file_read(self):
        result = run(_execute_bee_tool("file_read", {"path": "test.py"}, self.tmpdir))
        assert "def hello" in result
        assert "return 'world'" in result

    def test_file_read_absolute(self):
        path = os.path.join(self.tmpdir, "test.py")
        result = run(_execute_bee_tool("file_read", {"path": path}, self.tmpdir))
        assert "def hello" in result

    def test_file_read_not_found(self):
        result = run(_execute_bee_tool("file_read", {"path": "nonexistent.py"}, self.tmpdir))
        assert "not found" in result.lower()

    def test_file_read_with_offset(self):
        result = run(_execute_bee_tool("file_read", {"path": "test.py", "offset": 3, "limit": 1}, self.tmpdir))
        assert "print" in result
        assert "def hello" not in result

    def test_shell_exec(self):
        result = run(_execute_bee_tool("shell_exec", {"command": "echo hello_bee"}, self.tmpdir))
        assert "hello_bee" in result

    def test_shell_exec_stderr(self):
        result = run(_execute_bee_tool("shell_exec", {"command": "ls /nonexistent_dir_xyz"}, self.tmpdir))
        assert "stderr" in result.lower() or "no such" in result.lower()

    def test_shell_exec_cwd(self):
        result = run(_execute_bee_tool("shell_exec", {"command": "pwd"}, self.tmpdir))
        assert self.tmpdir in result

    def test_match_grep(self):
        result = run(_execute_bee_tool("match_grep", {"pattern": "hello", "directory": self.tmpdir}, self.tmpdir))
        assert "hello" in result

    def test_match_grep_no_matches(self):
        result = run(_execute_bee_tool("match_grep", {"pattern": "zzzznonexistent", "directory": self.tmpdir}, self.tmpdir))
        assert "no match" in result.lower() or result.strip() == ""

    def test_done_tool(self):
        result = run(_execute_bee_tool("done", {"result": "task complete"}, self.tmpdir))
        assert result == "task complete"

    def test_unknown_tool(self):
        result = run(_execute_bee_tool("fake_tool", {}, self.tmpdir))
        assert "unknown" in result.lower()


class TestBeeTools:
    """Tool definitions are well-formed."""

    def test_all_tools_have_names(self):
        for tool in EDDY_TOOLS:
            assert "function" in tool
            assert "name" in tool["function"]

    def test_done_tool_exists(self):
        names = [t["function"]["name"] for t in EDDY_TOOLS]
        assert "done" in names

    def test_file_read_exists(self):
        names = [t["function"]["name"] for t in EDDY_TOOLS]
        assert "file_read" in names

    def test_shell_exec_exists(self):
        names = [t["function"]["name"] for t in EDDY_TOOLS]
        assert "shell_exec" in names


class TestBeeResult:
    """Result dataclass."""

    def test_success_result(self):
        r = BeeResult(task="test", success=True, output="done", tool_calls=3, turns=5)
        assert r.success
        assert r.tool_calls == 3

    def test_failure_result(self):
        r = BeeResult(task="test", success=False, output="", error="timeout")
        assert not r.success
        assert r.error == "timeout"


class TestFormatSwarmResults:
    """Formatting for wave consumption."""

    def test_format_success(self):
        results = [
            BeeResult(task="read file", success=True, output="found 10 functions", tool_calls=2, turns=3, elapsed_ms=500),
            BeeResult(task="count lines", success=True, output="42 lines", tool_calls=1, turns=2, elapsed_ms=300),
        ]
        formatted = format_swarm_results(results)
        assert "2 eddies" in formatted
        assert "found 10 functions" in formatted
        assert "42 lines" in formatted
        assert "ok" in formatted

    def test_format_mixed(self):
        results = [
            BeeResult(task="good", success=True, output="result", tool_calls=1, turns=1, elapsed_ms=100),
            BeeResult(task="bad", success=False, output="", error="timeout", tool_calls=0, turns=1, elapsed_ms=5000),
        ]
        formatted = format_swarm_results(results)
        assert "ok" in formatted
        assert "FAIL" in formatted
        assert "timeout" in formatted

    def test_format_empty(self):
        formatted = format_swarm_results([])
        assert "0 eddies" in formatted

    def test_truncates_long_output(self):
        results = [
            BeeResult(task="t", success=True, output="x" * 10000, tool_calls=0, turns=1, elapsed_ms=100),
        ]
        formatted = format_swarm_results(results)
        assert len(formatted) < 10000
