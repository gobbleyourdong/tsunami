"""Tests for abort/interrupt handling ("""

import asyncio
import pytest

from tsunami.abort import AbortSignal, AbortError, create_combined_signal


class TestAbortSignal:
    """Flag-based abort signal."""

    def test_initial_state(self):
        sig = AbortSignal()
        assert sig.aborted is False
        assert sig.reason == ""

    def test_abort_sets_flag(self):
        sig = AbortSignal()
        sig.abort("user_interrupt")
        assert sig.aborted is True
        assert sig.reason == "user_interrupt"

    def test_abort_only_once(self):
        sig = AbortSignal()
        sig.abort("first")
        sig.abort("second")
        assert sig.reason == "first"  # first reason wins

    def test_check_raises_when_aborted(self):
        sig = AbortSignal()
        sig.check()  # should not raise
        sig.abort("test")
        with pytest.raises(AbortError) as exc_info:
            sig.check()
        assert "test" in str(exc_info.value)

    def test_check_passes_when_not_aborted(self):
        sig = AbortSignal()
        sig.check()  # should not raise

    def test_reset(self):
        sig = AbortSignal()
        sig.abort("test")
        assert sig.aborted is True
        sig.reset()
        assert sig.aborted is False
        assert sig.reason == ""

    def test_abort_time_recorded(self):
        import time
        sig = AbortSignal()
        before = time.time()
        sig.abort("test")
        after = time.time()
        assert before <= sig.abort_time <= after


class TestAbortError:
    """The exception raised on abort."""

    def test_contains_reason(self):
        err = AbortError("timeout")
        assert "timeout" in str(err)
        assert err.reason == "timeout"

    def test_default_reason(self):
        err = AbortError()
        assert err.reason == "aborted"


class TestAbortSignalAsync:
    """Async wait behavior."""

    def test_wait_returns_on_abort(self):
        async def _test():
            sig = AbortSignal()
            # Abort after tiny delay
            async def _abort():
                await asyncio.sleep(0.01)
                sig.abort("test")
            asyncio.create_task(_abort())
            result = await sig.wait(timeout=1.0)
            assert result is True
            assert sig.aborted is True

        asyncio.get_event_loop().run_until_complete(_test())

    def test_wait_timeout(self):
        async def _test():
            sig = AbortSignal()
            result = await sig.wait(timeout=0.01)
            assert result is False
            assert sig.aborted is False

        asyncio.get_event_loop().run_until_complete(_test())


class TestCombinedSignal:
    """Combined signal fires when any input fires."""

    def test_combined_fires_on_first(self):
        async def _test():
            a = AbortSignal()
            b = AbortSignal()
            combined = create_combined_signal(a, b)
            a.abort("from_a")
            await asyncio.sleep(0.2)  # let watcher detect
            assert combined.aborted is True
            assert combined.reason == "from_a"

        asyncio.get_event_loop().run_until_complete(_test())

    def test_combined_fires_on_second(self):
        async def _test():
            a = AbortSignal()
            b = AbortSignal()
            combined = create_combined_signal(a, b)
            b.abort("from_b")
            await asyncio.sleep(0.2)
            assert combined.aborted is True
            assert combined.reason == "from_b"

        asyncio.get_event_loop().run_until_complete(_test())

    def test_combined_not_aborted_initially(self):
        async def _test():
            a = AbortSignal()
            b = AbortSignal()
            combined = create_combined_signal(a, b)
            await asyncio.sleep(0.05)
            assert combined.aborted is False

        asyncio.get_event_loop().run_until_complete(_test())
