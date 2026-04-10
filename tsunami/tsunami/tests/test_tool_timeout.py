"""Tests for per-tool timeout with SIGKILL escalation."""

import asyncio
import pytest

from tsunami.tool_timeout import (
    get_timeout,
    run_with_timeout,
    ToolTimeoutError,
    ExecutionTimer,
    DEFAULT_TIMEOUTS,
    AUTO_BACKGROUND_THRESHOLD_S,
)


class TestGetTimeout:
    """Default timeout lookup by tool name."""

    def test_shell_exec(self):
        assert get_timeout("shell_exec") == 3600

    def test_file_read(self):
        assert get_timeout("file_read") == 30

    def test_match_grep(self):
        assert get_timeout("match_grep") == 20

    def test_unknown_tool_uses_default(self):
        assert get_timeout("unknown_tool") == DEFAULT_TIMEOUTS["default"]

    def test_all_defaults_positive(self):
        for tool, timeout in DEFAULT_TIMEOUTS.items():
            assert timeout > 0, f"{tool} has non-positive timeout"


class TestRunWithTimeout:
    """Async execution with timeout."""

    def test_fast_completes(self):
        async def _test():
            async def fast():
                return 42
            result = await run_with_timeout(fast(), "test_tool", timeout=5)
            assert result == 42
        asyncio.get_event_loop().run_until_complete(_test())

    def test_slow_raises_timeout(self):
        async def _test():
            async def slow():
                await asyncio.sleep(10)
            with pytest.raises(ToolTimeoutError) as exc_info:
                await run_with_timeout(slow(), "slow_tool", timeout=0.05)
            assert exc_info.value.tool_name == "slow_tool"
        asyncio.get_event_loop().run_until_complete(_test())

    def test_zero_timeout_no_limit(self):
        async def _test():
            async def fast():
                return "ok"
            result = await run_with_timeout(fast(), "test", timeout=0)
            assert result == "ok"
        asyncio.get_event_loop().run_until_complete(_test())

    def test_uses_default_timeout(self):
        """When timeout=None, uses tool-specific default."""
        async def _test():
            async def fast():
                return "ok"
            # This should use the default for "file_read" (30s) — won't timeout
            result = await run_with_timeout(fast(), "file_read")
            assert result == "ok"
        asyncio.get_event_loop().run_until_complete(_test())

    def test_timeout_error_has_details(self):
        err = ToolTimeoutError("my_tool", 30.0)
        assert "my_tool" in str(err)
        assert "30" in str(err)
        assert err.tool_name == "my_tool"
        assert err.timeout == 30.0


class TestExecutionTimer:
    """Track execution time for auto-background suggestions."""

    def test_initial_state(self):
        timer = ExecutionTimer()
        assert timer.elapsed == 0
        assert timer.should_suggest_background is False

    def test_tracks_elapsed(self):
        import time
        timer = ExecutionTimer()
        timer.start("shell_exec")
        time.sleep(0.05)
        assert timer.elapsed > 0.04

    def test_suggest_background_after_threshold(self):
        import time
        timer = ExecutionTimer()
        timer.start("shell_exec")
        # Fake elapsed time by manipulating start
        timer._start = time.time() - AUTO_BACKGROUND_THRESHOLD_S - 1
        assert timer.should_suggest_background is True

    def test_no_suggest_for_non_shell(self):
        import time
        timer = ExecutionTimer()
        timer.start("file_read")
        timer._start = time.time() - 100
        assert timer.should_suggest_background is False

    def test_format_elapsed_ms(self):
        timer = ExecutionTimer()
        timer.start("test")
        import time
        timer._start = time.time() - 0.5
        fmt = timer.format_elapsed()
        assert "ms" in fmt

    def test_format_elapsed_seconds(self):
        import time
        timer = ExecutionTimer()
        timer.start("test")
        timer._start = time.time() - 5
        fmt = timer.format_elapsed()
        assert "s" in fmt

    def test_format_elapsed_minutes(self):
        import time
        timer = ExecutionTimer()
        timer.start("test")
        timer._start = time.time() - 125
        fmt = timer.format_elapsed()
        assert "m" in fmt
