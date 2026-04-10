"""Abort/interrupt handling — graceful cleanup on cancellation.

Provides a way to interrupt the agent loop mid-execution, ensuring:
- Running tool gets a chance to clean up
- Partial results are saved to state
- Session is persisted on abort (no lost work)

Uses asyncio cancellation with a flag-based approach (Python doesn't have
AbortController like JS, but asyncio.Event + cancellation achieves the same).
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger("tsunami.abort")


class AbortSignal:
    """Flag-based abort signal (Python equivalent of JS AbortController).

    Can be triggered from any thread/coroutine. Once aborted, stays aborted.
    Supports multiple triggers (combined signal pattern ).
    """

    def __init__(self):
        self._aborted = False
        self._reason: str = ""
        self._event = asyncio.Event()
        self._abort_time: float = 0

    @property
    def aborted(self) -> bool:
        return self._aborted

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def abort_time(self) -> float:
        return self._abort_time

    def abort(self, reason: str = "user_interrupt"):
        """Trigger the abort signal."""
        if not self._aborted:
            self._aborted = True
            self._reason = reason
            self._abort_time = time.time()
            self._event.set()
            log.info(f"Abort signal triggered: {reason}")

    async def wait(self, timeout: float | None = None) -> bool:
        """Wait for abort signal. Returns True if aborted, False on timeout."""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def check(self) -> None:
        """Check if aborted, raise if so. Use in tool execution loops."""
        if self._aborted:
            raise AbortError(self._reason)

    def reset(self):
        """Reset for reuse (between agent runs)."""
        self._aborted = False
        self._reason = ""
        self._abort_time = 0
        self._event.clear()


class AbortError(Exception):
    """Raised when an operation is aborted."""

    def __init__(self, reason: str = "aborted"):
        self.reason = reason
        super().__init__(f"Operation aborted: {reason}")


def create_combined_signal(*signals: AbortSignal) -> AbortSignal:
    """Create a signal that fires when ANY of the input signals fire.

    ts — useful when you need
    both a user interrupt AND a timeout to cancel the same operation.
    """
    combined = AbortSignal()

    async def _watch():
        while not combined.aborted:
            for s in signals:
                if s.aborted:
                    combined.abort(s.reason)
                    return
            await asyncio.sleep(0.1)

    # Fire-and-forget watcher
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_watch())
    except RuntimeError:
        pass  # No running loop — signals will be checked manually

    return combined


def create_timeout_signal(timeout_seconds: float) -> AbortSignal:
    """Create a signal that auto-fires after a timeout.

    Useful for tool execution timeouts.
    """
    signal = AbortSignal()

    async def _timeout():
        await asyncio.sleep(timeout_seconds)
        if not signal.aborted:
            signal.abort(f"timeout_{timeout_seconds}s")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_timeout())
    except RuntimeError:
        pass

    return signal
