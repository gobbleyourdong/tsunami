"""realtime delivery gate — two-client WebSocket roundtrip.

Pattern the realtime scaffold is built for (live cursors, shared
whiteboard, presence list) requires that a message sent by one client
fans out to the others. This probe spawns the server, connects two
WebSocket clients, sends a tagged message from A, and asserts B
receives it within a deadline.

Failure modes caught:
  - Server doesn't start (same as server_probe)
  - WS upgrade path wrong (server listens on HTTP only)
  - Broadcast logic missing (only client A sees its own echo)
  - Latency pathological (>1s is a design bug, not a network blip)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from ._probe_common import (
    free_port,
    result,
    skip,
    spawn_child,
    terminate_child,
    wait_for_http,
    drain_output,
)


async def _open_ws(url: str, open_timeout_s: float):
    """Import-lazy wrapper so the module loads even without websockets."""
    try:
        import websockets
    except ImportError:
        return None, "websockets library not installed"
    try:
        # websockets>=11 api: `websockets.connect` is an awaitable context
        # manager. For probe semantics we want to own the connect step and
        # close manually, so use the low-level client.
        ws = await asyncio.wait_for(
            websockets.connect(url, open_timeout=open_timeout_s),
            timeout=open_timeout_s,
        )
        return ws, ""
    except asyncio.TimeoutError:
        return None, f"ws connect timed out after {open_timeout_s}s"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


async def _recv_until_tagged(ws, tag: str, deadline_s: float) -> tuple[bool, str]:
    """Read messages until we see `tag` or the deadline passes.

    Echoes from A that leak back to A are fine; we key on `tag`, not on
    the other client's message count, so a broadcast-to-all server is
    indistinguishable from a broadcast-to-others. Good enough for the
    gate's purpose.
    """
    loop = asyncio.get_event_loop()
    end = loop.time() + deadline_s
    last_seen = ""
    while loop.time() < end:
        remaining = end - loop.time()
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=max(0.05, remaining))
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            return False, f"recv error: {e}"
        last_seen = str(msg)[:200]
        if tag in last_seen:
            return True, last_seen
    return False, last_seen


async def ws_probe(
    project_dir: Path,
    start_cmd: str = "npm run server",
    ws_path: str = "/",
    boot_timeout_s: float = 20.0,
    roundtrip_deadline_s: float = 1.5,
    port: int | None = None,
) -> dict:
    """Spawn → wait for port → connect 2 WS → send → assert B sees it.

    `ws_path` defaults to '/'. Some servers mount ws on '/ws' or
    '/socket'; callers override as needed.
    """
    project_dir = Path(project_dir)
    if not (project_dir / "package.json").is_file():
        return skip(f"no package.json in {project_dir}")

    p = port or free_port()
    env = {"PORT": str(p), "HOST": "127.0.0.1"}
    proc = await spawn_child(start_cmd, project_dir, env)
    try:
        http_base = f"http://127.0.0.1:{p}"
        reachable, _ = await wait_for_http(
            http_base + "/",
            timeout_s=boot_timeout_s,
            expect_status=(200, 204, 301, 302, 400, 401, 403, 404, 426),
        )
        tail = await drain_output(proc)
        if not reachable:
            rc = proc.returncode
            note = (f"server exited (returncode={rc})" if rc is not None
                    else f"server did not bind within {boot_timeout_s}s")
            return result(False, note, raw=tail[-1000:])

        ws_url = f"ws://127.0.0.1:{p}{ws_path}"
        ws_a, err_a = await _open_ws(ws_url, open_timeout_s=3.0)
        if ws_a is None:
            return result(False, f"client A could not connect to {ws_url}: {err_a}",
                          raw=tail[-400:])
        ws_b, err_b = await _open_ws(ws_url, open_timeout_s=3.0)
        if ws_b is None:
            try:
                await ws_a.close()
            except Exception:
                pass
            return result(False, f"client B could not connect to {ws_url}: {err_b}",
                          raw=tail[-400:])

        try:
            tag = f"tsunami-probe-{uuid.uuid4().hex[:8]}"
            payload = json.dumps({"type": "probe", "tag": tag})
            try:
                await ws_a.send(payload)
            except Exception as e:
                return result(False, f"client A failed to send: {e}")

            got, last = await _recv_until_tagged(ws_b, tag,
                                                 deadline_s=roundtrip_deadline_s)
            if not got:
                return result(
                    False,
                    f"client B did not receive broadcast within {roundtrip_deadline_s}s — broadcast logic missing?",
                    raw=f"last seen by B: {last!r}",
                )
            return result(True, "", raw=f"roundtrip ok (tag={tag})")
        finally:
            for ws in (ws_a, ws_b):
                try:
                    await ws.close()
                except Exception:
                    pass
    finally:
        await terminate_child(proc)


__all__ = ["ws_probe"]
