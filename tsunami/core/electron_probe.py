"""electron-app delivery gate — build + artifact check (no GUI).

The user-facing failure for most electron-app deliveries is "the app
won't open". That breaks down into:
  1. Build failed (tsc / vite / rollup errored)
  2. Build succeeded but main-process entry is missing
  3. preload.ts bundled with nodeIntegration leaks (v1 security smell)

We can catch all three without launching electron-builder's actual
packager (which is slow and pulls 200 MB of cache per run) and without
opening a window. Run `npm run build`, then sanity-check what landed
in dist/ against the package.json `main` field.

This is the "electron-builder --dry" equivalent the user specified:
exercise the compile pipeline, verify the artifacts, skip the GUI.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from ._probe_common import result, skip


_BAD_PATTERNS = (
    (re.compile(r"nodeIntegration\s*:\s*true", re.I), "nodeIntegration:true — disable (use contextBridge + preload)"),
    (re.compile(r"contextIsolation\s*:\s*false", re.I), "contextIsolation:false — v1 security smell"),
    (re.compile(r"webPreferences\s*:\s*\{\s*\}", re.I), "empty webPreferences — set contextIsolation:true explicitly"),
)


async def electron_probe(project_dir: Path,
                         build_cmd: str = "npm run build",
                         timeout_s: int = 180) -> dict:
    """Run the electron build pipeline, verify artifacts, static-scan
    the renderer config for known-bad patterns.
    """
    project_dir = Path(project_dir)
    pkg_path = project_dir / "package.json"
    if not pkg_path.is_file():
        return result(False, "package.json missing", raw=str(pkg_path))

    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return result(False, f"package.json not valid JSON: {e}")

    main_ref = pkg.get("main")
    if not main_ref:
        return result(False, "package.json has no 'main' field — electron won't know which file to load")

    # SECURITY (sev-5 class patch, 2026-04-21): argv-list form via
    # create_subprocess_exec, not shell interpolation. Previous
    # `f"{build_cmd} 2>&1"` ran through /bin/sh — if build_cmd ever
    # gets constructed from attacker input, that's an RCE. stderr
    # already merges into stdout via stderr=STDOUT so the 2>&1 was
    # redundant. Closes probe_shell_pattern class (Current finding).
    import shlex
    argv = shlex.split(build_cmd)
    if not argv:
        return result(False, f"build_cmd empty after shlex.split: {build_cmd!r}")
    spawn = asyncio.create_subprocess_exec
    proc = await spawn(
        *argv,
        cwd=str(project_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout_b, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return result(False, f"build timed out after {timeout_s}s", raw="(timeout)")
    output = stdout_b.decode("utf-8", errors="replace")

    issues: list[str] = []
    if proc.returncode != 0:
        tail = output[-800:] if len(output) > 800 else output
        return result(False, f"{build_cmd} exited {proc.returncode}", raw=tail)

    # Main-process entry must exist post-build.
    main_path = project_dir / main_ref
    if not main_path.is_file():
        issues.append(f"main entry '{main_ref}' missing after build")

    # Preload, if declared, must exist too.
    preload_ref = (pkg.get("electron") or {}).get("preload") or pkg.get("preload")
    if isinstance(preload_ref, str):
        preload_path = project_dir / preload_ref
        if not preload_path.is_file():
            issues.append(f"preload '{preload_ref}' missing after build")

    # Scan main + any BrowserWindow config source for security smells.
    scan_targets: list[Path] = []
    if main_path.is_file():
        scan_targets.append(main_path)
    for candidate in ("electron/main.ts", "electron/main.js",
                      "src/main.ts", "src/main/index.ts"):
        p = project_dir / candidate
        if p.is_file() and p not in scan_targets:
            scan_targets.append(p)

    for target in scan_targets:
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat, msg in _BAD_PATTERNS:
            if pat.search(text):
                issues.append(f"{target.name}: {msg}")

    passed = not issues
    return result(
        passed,
        issues="; ".join(issues),
        raw=output[-1200:] if output else "",
    )


__all__ = ["electron_probe"]
