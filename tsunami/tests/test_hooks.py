"""Tests for hook system ("""

import asyncio
import json
import os
import tempfile
import pytest

from tsunami.hooks import (
    HookRegistry, HookConfig, HookResult, HookEvent, HookOutcome,
    execute_hook, execute_hooks,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestHookRegistry:
    """Hook registration and lookup."""

    def test_register_and_get(self):
        reg = HookRegistry()
        hook = HookConfig(type="command", command="echo test")
        reg.register(HookEvent.PRE_TOOL_USE, hook)
        hooks = reg.get_hooks(HookEvent.PRE_TOOL_USE)
        assert len(hooks) == 1

    def test_matcher_filter(self):
        reg = HookRegistry()
        reg.register("PreToolUse", HookConfig(type="command", matcher="shell_exec", command="check.sh"))
        reg.register("PreToolUse", HookConfig(type="command", matcher="file_write", command="audit.sh"))
        reg.register("PreToolUse", HookConfig(type="command", command="all.sh"))  # no matcher

        shell_hooks = reg.get_hooks("PreToolUse", tool_name="shell_exec")
        assert len(shell_hooks) == 2  # matcher match + no-matcher

        file_hooks = reg.get_hooks("PreToolUse", tool_name="file_write")
        assert len(file_hooks) == 2

    def test_function_hook(self):
        reg = HookRegistry()
        reg.register_function(HookEvent.POST_TOOL_USE, lambda data: HookResult())
        hooks = reg.get_hooks(HookEvent.POST_TOOL_USE)
        assert len(hooks) == 1
        assert hooks[0].type == "function"

    def test_clear_session_hooks(self):
        reg = HookRegistry()
        reg.register("PreToolUse", HookConfig(type="command", command="persistent.sh"))
        reg.register_function("PreToolUse", lambda d: None)
        assert reg.count == 2
        reg.clear_session_hooks()
        assert reg.count == 1  # only command hook remains

    def test_count(self):
        reg = HookRegistry()
        reg.register("A", HookConfig(type="command", command="a"))
        reg.register("B", HookConfig(type="command", command="b"))
        reg.register_function("A", lambda d: None)
        assert reg.count == 3


class TestHookRegistryFromFile:
    """Load hooks from JSON config."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_load_valid_config(self):
        config = {
            "PreToolUse": [
                {"type": "command", "matcher": "shell_exec", "command": "validate.sh"},
            ],
            "PostToolUse": [
                {"type": "command", "command": "log.sh"},
            ],
        }
        path = os.path.join(self.tmpdir, "hooks.json")
        with open(path, "w") as f:
            json.dump(config, f)

        reg = HookRegistry()
        reg.load_from_file(path)
        assert len(reg.get_hooks("PreToolUse")) == 1
        assert len(reg.get_hooks("PostToolUse")) == 1

    def test_load_nonexistent(self):
        reg = HookRegistry()
        reg.load_from_file("/nonexistent/hooks.json")
        assert reg.count == 0

    def test_load_invalid_json(self):
        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w") as f:
            f.write("not json")
        reg = HookRegistry()
        reg.load_from_file(path)
        assert reg.count == 0


class TestExecuteHooks:
    """Hook execution — command and function types."""

    def test_function_hook_success(self):
        hook = HookConfig(
            type="function",
            callback=lambda data: HookResult(outcome=HookOutcome.SUCCESS, message="ok"),
        )
        result = run(execute_hook(hook, {"tool": "test"}))
        assert result.outcome == HookOutcome.SUCCESS

    def test_function_hook_dict_return(self):
        hook = HookConfig(
            type="function",
            callback=lambda data: {"outcome": "success", "message": "from dict"},
        )
        result = run(execute_hook(hook, {}))
        assert result.outcome == HookOutcome.SUCCESS
        assert result.message == "from dict"

    def test_function_hook_none_return(self):
        hook = HookConfig(type="function", callback=lambda data: None)
        result = run(execute_hook(hook, {}))
        assert result.outcome == HookOutcome.SUCCESS

    def test_function_hook_crash(self):
        def crasher(data):
            raise ValueError("boom")
        hook = HookConfig(type="function", callback=crasher)
        result = run(execute_hook(hook, {}))
        assert result.outcome == HookOutcome.NON_BLOCKING_ERROR
        assert "boom" in result.message

    def test_async_function_hook(self):
        async def async_hook(data):
            return HookResult(message="async works")
        hook = HookConfig(type="function", callback=async_hook)
        result = run(execute_hook(hook, {}))
        assert result.message == "async works"

    def test_command_hook_success(self):
        hook = HookConfig(type="command", command="echo hello")
        result = run(execute_hook(hook, {"test": True}))
        assert result.outcome == HookOutcome.SUCCESS

    def test_command_hook_exit_2_blocks(self):
        hook = HookConfig(type="command", command="exit 2")
        result = run(execute_hook(hook, {}))
        assert result.outcome == HookOutcome.BLOCKING

    def test_command_hook_exit_1_non_blocking(self):
        hook = HookConfig(type="command", command="exit 1")
        result = run(execute_hook(hook, {}))
        assert result.outcome == HookOutcome.NON_BLOCKING_ERROR

    def test_command_hook_timeout(self):
        hook = HookConfig(type="command", command="sleep 10", timeout=1)
        result = run(execute_hook(hook, {}))
        assert result.outcome == HookOutcome.NON_BLOCKING_ERROR
        assert "timed out" in result.message

    def test_execute_multiple_hooks(self):
        reg = HookRegistry()
        reg.register_function("Test", lambda d: HookResult(message="first"))
        reg.register_function("Test", lambda d: HookResult(message="second"))
        results = run(execute_hooks(reg, "Test", {}))
        assert len(results) == 2
        assert results[0].message == "first"
        assert results[1].message == "second"

    def test_execute_no_hooks(self):
        reg = HookRegistry()
        results = run(execute_hooks(reg, "NoEvent", {}))
        assert results == []

    def test_invalid_hook_type(self):
        hook = HookConfig(type="unknown")
        result = run(execute_hook(hook, {}))
        assert result.outcome == HookOutcome.NON_BLOCKING_ERROR
