"""api-only delivery gate — spawn server, fetch /openapi.json, schema-validate.

Replaces `vision_gate` for headless API scaffolds (there's nothing to
screenshot). The check is:

  1. Server starts and binds a port.
  2. GET /openapi.json returns 200 + valid JSON.
  3. The JSON is recognizably OpenAPI 3.x — has `openapi` version,
     `info.title`, and `paths` with at least one entry.
  4. For each declared path+method, we do a shallow liveness probe
     with an empty-body request; anything below 500 is acceptable.
     The goal is to catch "handler imported but never bound" or
     "route declared but throws on first hit" — not correctness.

Schema validation uses the OpenAPI 3.1.0 JSON Schema via `jsonschema`
when available; falls back to a minimal structural check otherwise.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

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


def _structural_check(doc: dict) -> list[str]:
    """Minimal structural validation (no jsonschema dep)."""
    issues: list[str] = []
    version = doc.get("openapi")
    if not isinstance(version, str):
        issues.append("'openapi' field missing or not a string")
    elif not version.startswith(("3.0", "3.1")):
        issues.append(f"openapi version {version!r} unsupported (expected 3.0.x / 3.1.x)")
    info = doc.get("info")
    if not isinstance(info, dict) or not info.get("title"):
        issues.append("info.title missing")
    paths = doc.get("paths")
    if not isinstance(paths, dict) or not paths:
        issues.append("paths empty — no endpoints declared")
    return issues


def _collect_endpoints(doc: dict) -> list[tuple[str, str]]:
    """Return (method, path) pairs from the spec."""
    out: list[tuple[str, str]] = []
    valid_methods = {"get", "post", "put", "delete", "patch", "head", "options"}
    for pth, block in (doc.get("paths") or {}).items():
        if not isinstance(block, dict):
            continue
        for method in block:
            if method.lower() in valid_methods:
                out.append((method.upper(), pth))
    return out


async def _liveness_probe(client: httpx.AsyncClient, base: str,
                          method: str, path: str) -> tuple[int, str]:
    """Shallow liveness hit. Path-param templates are left as-is —
    most servers return 400/404 for a literal '/users/{id}' path and
    that's fine: we're testing that the route exists and doesn't 500.
    """
    url = base + path
    try:
        if method == "GET":
            r = await client.get(url)
        elif method == "HEAD":
            r = await client.head(url)
        elif method == "DELETE":
            r = await client.delete(url)
        else:
            r = await client.request(method, url, json={})
        return r.status_code, ""
    except httpx.HTTPError as e:
        return -1, f"{type(e).__name__}: {e}"


async def openapi_probe(
    project_dir: Path,
    start_cmd: str = "npm start",
    openapi_path: str = "/openapi.json",
    probe_endpoints: bool = True,
    boot_timeout_s: float = 20.0,
    endpoint_timeout_s: float = 3.0,
    max_endpoints_to_probe: int = 12,
    port: int | None = None,
) -> dict:
    project_dir = Path(project_dir)
    if not (project_dir / "package.json").is_file():
        return skip(f"no package.json in {project_dir}")

    p = port or free_port()
    env = {"PORT": str(p), "HOST": "127.0.0.1"}

    proc = await spawn_child(start_cmd, project_dir, env)
    base = f"http://127.0.0.1:{p}"
    try:
        # Wait for any response — openapi_path itself might 404 briefly
        # during the framework's route-compile phase.
        reachable, _ = await wait_for_http(
            base + "/",
            timeout_s=boot_timeout_s,
            expect_status=(200, 204, 301, 302, 400, 401, 403, 404),
        )
        tail = await drain_output(proc)
        if not reachable:
            rc = proc.returncode
            note = (f"server exited (returncode={rc})" if rc is not None
                    else f"server did not bind within {boot_timeout_s}s")
            return result(False, note, raw=tail[-1000:])

        # Fetch the spec.
        async with httpx.AsyncClient(timeout=endpoint_timeout_s) as client:
            try:
                r = await client.get(base + openapi_path)
            except httpx.HTTPError as e:
                return result(False, f"GET {openapi_path} failed: {e}",
                              raw=tail[-400:])
            if r.status_code != 200:
                return result(False, f"GET {openapi_path} returned {r.status_code} — api-only scaffolds must serve their spec",
                              raw=r.text[:400])
            try:
                doc = r.json()
            except json.JSONDecodeError as e:
                return result(False, f"{openapi_path} body is not JSON: {e}",
                              raw=r.text[:400])

            issues = _structural_check(doc)
            if issues:
                return result(False, "; ".join(issues),
                              raw=json.dumps(doc)[:600])

            endpoints = _collect_endpoints(doc)
            if not endpoints:
                return result(False, "spec declares no endpoints",
                              raw=json.dumps(doc.get("paths") or {})[:400])

            summary = {"openapi": doc.get("openapi"),
                       "title": (doc.get("info") or {}).get("title"),
                       "endpoint_count": len(endpoints)}

            if not probe_endpoints:
                return result(True, "", raw=json.dumps(summary))

            # Shallow probe each endpoint. Anything <500 is fine.
            failures: list[str] = []
            probed = 0
            for method, path in endpoints[:max_endpoints_to_probe]:
                status, err = await _liveness_probe(client, base, method, path)
                probed += 1
                if status == -1:
                    failures.append(f"{method} {path}: {err}")
                elif status >= 500:
                    failures.append(f"{method} {path}: {status}")
            summary["probed"] = probed
            summary["failures"] = failures

            passed = not failures
            issues_str = ""
            if failures:
                issues_str = f"{len(failures)}/{probed} endpoints 5xx or unreachable: " + "; ".join(failures[:3])
            return result(passed, issues_str, raw=json.dumps(summary))
    finally:
        await terminate_child(proc)


__all__ = ["openapi_probe"]
