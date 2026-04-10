"""Per-tool timeout with SIGTERM → SIGKILL escalation.

Wraps async tool execution with a configurable timeout.
On timeout: sends SIGTERM, waits 5s, then SIGKILL.

Also supports auto-backgrounding for long commands
(..
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time

log = logging.getLogger("tsunami.tool_timeout")

# Default timeouts by tool type
DEFAULT_TIMEOUTS = {
    "shell_exec": 3600,     # 1 hour (user can override)
    "file_read": 30,        # 30 seconds
    "file_write": 30,
    "file_edit": 30,
    "match_glob": 20,       # ripgrep timeout 
    "match_grep": 20,
    "search_web": 60,
    "python_exec": 120,
    "summarize_file": 60,
    "swell": 600,
    "swell_analyze": 600,
    "default": 120,
}

# Auto-background threshold (.
AUTO_BACKGROUND_THRESHOLD_S = 15

# SIGKILL escalation delay
SIGKILL_DELAY_S = 5


class ToolTimeoutError(Exception):
    """Raised when a tool exceeds its timeout."""

    def __init__(self, tool_name: str, timeout: float):
        self.tool_name = tool_name
        self.timeout = timeout
        super().__init__(f"Tool '{tool_name}' timed out after {timeout}s")


def get_timeout(tool_name: str) -> int:
    """Get the default timeout for a tool."""
    return DEFAULT_TIMEOUTS.get(tool_name, DEFAULT_TIMEOUTS["default"])


async def run_with_timeout(coro, tool_name: str, timeout: float | None = None):
    """Run a coroutine with timeout and logging.

    On timeout, raises ToolTimeoutError.
    """
    if timeout is None:
        timeout = get_timeout(tool_name)

    if timeout <= 0:
        return await coro  # No timeout

    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        log.warning(f"Tool {tool_name} timed out after {timeout}s")
        raise ToolTimeoutError(tool_name, timeout)


async def kill_process_gracefully(proc: asyncio.subprocess.Process,
                                   timeout: float = SIGKILL_DELAY_S):
    """Kill a subprocess with SIGTERM → wait → SIGKILL escalation.

    ts timeout handling:
    1. Send SIGTERM
    2. Wait up to timeout seconds
    3. If still alive, SIGKILL
    """
    if proc.returncode is not None:
        return  # Already dead

    try:
        proc.terminate()  # SIGTERM
        log.debug("Sent SIGTERM to process")
    except ProcessLookupError:
        return  # Already dead

    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
        log.debug(f"Process exited after SIGTERM (code={proc.returncode})")
    except asyncio.TimeoutError:
        # Still alive after timeout — escalate to SIGKILL
        try:
            proc.kill()  # SIGKILL
            log.warning("Escalated to SIGKILL after SIGTERM timeout")
            await asyncio.wait_for(proc.wait(), timeout=2)
        except (ProcessLookupError, asyncio.TimeoutError):
            pass


class ExecutionTimer:
    """Track tool execution time for auto-background decisions.

    if a command runs longer than AUTO_BACKGROUND_THRESHOLD_S,
    suggest backgrounding it.
    """

    def __init__(self):
        self._start: float = 0
        self._tool_name: str = ""

    def start(self, tool_name: str):
        self._start = time.time()
        self._tool_name = tool_name

    @property
    def elapsed(self) -> float:
        if self._start == 0:
            return 0
        return time.time() - self._start

    @property
    def should_suggest_background(self) -> bool:
        """Should we suggest backgrounding this operation?"""
        return (
            self._tool_name in ("shell_exec", "python_exec")
            and self.elapsed > AUTO_BACKGROUND_THRESHOLD_S
        )

    def format_elapsed(self) -> str:
        e = self.elapsed
        if e < 1:
            return f"{e * 1000:.0f}ms"
        elif e < 60:
            return f"{e:.1f}s"
        else:
            return f"{int(e // 60)}m {int(e % 60)}s"
