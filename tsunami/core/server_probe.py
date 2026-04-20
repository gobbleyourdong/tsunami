"""auth-app / fullstack delivery gate — spawn server, hit /health, kill.

These scaffolds ship a client *and* a server. The vision-gate covers
the client (screenshot of the built SPA). This probe covers the
server: can it start, bind a port, and answer a health endpoint
without crashing?

Key design points:
  - We pick the port (ephemeral) and inject it via `PORT` env var.
    Every reasonable Node HTTP framework reads PORT; drones are
    prompted to do the same.
  - We spawn via shell in a new process group so `npm` -> `node` ->
    user-code is torn down as a unit (see `_probe_common.terminate_child`).
  - Health path defaults to `/health`. For servers that don't ship one
    yet, a 404 still counts as "server bound" — a dead server would
    ConnectError. The probe reports 404 as a soft issue so the drone
    knows to add the endpoint.
"""

from __future__ import annotations

from pathlib import Path
import asyncio

import httpx

from ._probe_common import (
    free_port,
    result,
    skip,
    spawn_child,
    terminate_child,
    wait_for_http,
    drain_output,
)


async def server_probe(
    project_dir: Path,
    start_cmd: str = "npm run server",
    health_path: str = "/health",
    boot_timeout_s: float = 20.0,
    health_timeout_s: float = 4.0,
    port: int | None = None,
) -> dict:
    """Spawn the server in `project_dir`, poll `/health`, kill.

    Args:
      project_dir: path to the delivery. Must contain package.json.
      start_cmd: shell command that starts the server in foreground.
                 Default 'npm run server' (convention for auth-app /
                 fullstack scaffolds).
      health_path: endpoint to hit. 404 → reported as soft issue.
      boot_timeout_s: how long to wait for the port to become
                      reachable before giving up.
      port: force a specific port (mostly for tests). None → pick
            free port and export it as `PORT`.

    Returns ProbeResult. `passed=True` means the server bound AND
    /health returned 2xx/3xx. `passed=False` with an issues string
    otherwise.
    """
    project_dir = Path(project_dir)
    if not (project_dir / "package.json").is_file():
        return skip(f"no package.json in {project_dir}")

    p = port or free_port()
    env = {"PORT": str(p), "HOST": "127.0.0.1"}

    proc = await spawn_child(start_cmd, project_dir, env)
    try:
        base = f"http://127.0.0.1:{p}"
        reachable, root_status = await wait_for_http(
            base + "/",
            timeout_s=boot_timeout_s,
            # Any response at all proves the child bound the port.
            expect_status=(200, 204, 301, 302, 400, 401, 403, 404),
        )
        tail = await drain_output(proc)
        if not reachable:
            if proc.returncode is not None:
                return result(
                    False,
                    f"server exited before binding (returncode={proc.returncode}) — run '{start_cmd}' locally to see the stack",
                    raw=tail[-1000:],
                )
            return result(
                False,
                f"server did not bind port {p} within {boot_timeout_s}s — check the start command or PORT handling",
                raw=tail[-1000:],
            )

        # Server is up — query the real health endpoint.
        try:
            async with httpx.AsyncClient(timeout=health_timeout_s) as client:
                r = await client.get(base + health_path)
                hstatus = r.status_code
                hbody = r.text[:400]
        except Exception as e:
            return result(False, f"server bound but {health_path} errored: {e}",
                          raw=tail[-800:])

        issues: list[str] = []
        if hstatus == 404:
            issues.append(f"{health_path} returned 404 — add a liveness endpoint")
        elif hstatus >= 500:
            issues.append(f"{health_path} returned {hstatus} — server-side error")
        elif hstatus >= 400:
            issues.append(f"{health_path} returned {hstatus}")
        passed = not issues
        return result(passed, "; ".join(issues),
                      raw=f"GET {health_path} -> {hstatus}\n{hbody}")
    finally:
        await terminate_child(proc)


__all__ = ["server_probe"]
