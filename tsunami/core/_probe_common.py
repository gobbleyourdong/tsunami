"""Shared helpers for delivery-gate probes.

Keep this module dependency-light: stdlib + httpx only. Each probe
spawns its own child process and needs an ephemeral port; the helpers
below guarantee per-invocation isolation so N probes can run in
parallel from different wave instances without collision.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import socket
from pathlib import Path
from typing import Awaitable, Callable

import httpx

log = logging.getLogger("tsunami.core.probe")


def free_port() -> int:
    """Bind to port 0, read back the OS-assigned port, release it.

    Race window: the port is free for ~microseconds between the caller
    receiving it and the child binding to it. In practice the kernel
    does not re-hand-out the same port that quickly; probe callers
    accept the risk (same pattern as vision_gate._screenshot_html).
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def wait_for_http(
    url: str,
    timeout_s: float = 10.0,
    interval_s: float = 0.15,
    expect_status: tuple[int, ...] = (200, 204, 301, 302, 404),
) -> tuple[bool, int]:
    """Poll `url` until it responds or we run out of time.

    Returns (reachable, last_status). `reachable` is True if we got
    any response in expect_status; `last_status` is -1 if no response
    ever landed (child didn't bind).

    404 counts as reachable: we're probing liveness, not correctness.
    Individual probes re-query the specific endpoint they care about
    once this returns True.
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    last_status = -1
    async with httpx.AsyncClient(timeout=interval_s * 4) as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await client.get(url)
                last_status = r.status_code
                if r.status_code in expect_status:
                    return True, r.status_code
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                pass
            except Exception as e:
                log.debug(f"wait_for_http transient {url}: {e}")
            await asyncio.sleep(interval_s)
    return False, last_status


async def spawn_child(
    cmd: str,
    cwd: Path,
    env_extra: dict[str, str] | None = None,
) -> asyncio.subprocess.Process:
    """Spawn `cmd` in a new process group so we can kill the whole tree.

    `npm run …` forks node under a shell, which forks again for user
    code. A plain `proc.kill()` only reaps the shell; the server child
    keeps its port. `start_new_session=True` + `killpg` tears down
    everything in one signal.
    """
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return await asyncio.create_subprocess_shell(
        cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )


async def terminate_child(
    proc: asyncio.subprocess.Process,
    grace_s: float = 1.5,
) -> None:
    """SIGTERM the whole process group, escalate to SIGKILL if needed."""
    if proc.returncode is not None:
        return
    pgid = None
    with contextlib.suppress(ProcessLookupError, OSError):
        pgid = os.getpgid(proc.pid)
    if pgid is not None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pgid, signal.SIGTERM)
    try:
        await asyncio.wait_for(proc.wait(), timeout=grace_s)
    except asyncio.TimeoutError:
        if pgid is not None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pgid, signal.SIGKILL)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), timeout=grace_s)


async def drain_output(proc: asyncio.subprocess.Process, limit: int = 4000) -> str:
    """Read whatever's on the child's stdout pipe without blocking.

    We don't fully `await proc.communicate()` — the child is still
    running when the probe wants a snapshot. Read until the buffer is
    empty or we hit `limit` bytes, whichever comes first.
    """
    if proc.stdout is None:
        return ""
    chunks: list[bytes] = []
    total = 0
    try:
        while total < limit:
            try:
                chunk = await asyncio.wait_for(proc.stdout.read(512), timeout=0.05)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except Exception:
        pass
    return b"".join(chunks).decode("utf-8", errors="replace")


async def with_child(
    cmd: str,
    cwd: Path,
    env_extra: dict[str, str] | None,
    body: Callable[[asyncio.subprocess.Process], Awaitable[dict]],
) -> dict:
    """Spawn → body(proc) → always kill.

    The body coroutine owns the probe logic: wait for readiness, hit
    whatever endpoint, return a ProbeResult dict.
    """
    proc = await spawn_child(cmd, cwd, env_extra)
    try:
        return await body(proc)
    finally:
        await terminate_child(proc)


def result(passed: bool, issues: str = "", raw: str = "") -> dict:
    """Canonical probe-result shape. Matches vision_gate.vision_check."""
    return {"passed": bool(passed), "issues": issues or "", "raw": raw or ""}


def skip(reason: str) -> dict:
    """Fall-through result: gate unavailable, don't block delivery."""
    return {"passed": True, "issues": "", "raw": f"(skip: {reason})"}
