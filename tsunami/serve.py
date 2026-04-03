"""Serve — the good dev port.

One port. Every project. Kill what's there, serve what's new.
React/TS projects get Vite. Static files get http.server.
The user never thinks about this.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
from pathlib import Path

log = logging.getLogger("tsunami.serve")

DEV_PORT = int(os.environ.get("TSUNAMI_DEV_PORT", "9876"))


def _kill_port(port: int):
    """Kill whatever is listening on this port (cross-platform)."""
    import sys
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "LISTENING" not in line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                local_addr = parts[1]
                if ":" in local_addr:
                    candidate = local_addr.rsplit(":", 1)[-1]
                    if candidate.isdigit() and int(candidate) == port:
                        pid = parts[-1]
                        if pid.isdigit():
                            subprocess.run(["taskkill", "/PID", pid, "/F"],
                                           capture_output=True, timeout=5)
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsof", "-t", f"-i:{port}"],
                capture_output=True, text=True, timeout=5,
            )
            pids = result.stdout.strip().split()
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except (ProcessLookupError, ValueError):
                    pass
        except Exception:
            pass


def _is_vite_project(project_dir: str) -> bool:
    """Does this project have a package.json with vite?"""
    pkg = Path(project_dir) / "package.json"
    if not pkg.exists():
        return False
    try:
        import json
        data = json.loads(pkg.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        return "vite" in deps
    except Exception:
        return False


def _is_html_project(project_dir: str) -> bool:
    """Does this project have an index.html at root?"""
    return (Path(project_dir) / "index.html").exists()


_current_project = None

def serve_project(project_dir: str, port: int = DEV_PORT) -> str:
    """Serve a project on the dev port.

    If the same project is already being served, do nothing (Vite HMR handles updates).
    If a different project, kill the old server and start new.
    """
    global _current_project

    # Already serving this project — Vite HMR handles file changes
    if _current_project == project_dir:
        return f"http://localhost:{port}"

    _kill_port(port)
    _current_project = project_dir

    import time
    time.sleep(0.5)

    import sys as _sys
    shell = _sys.platform == "win32"
    if _is_vite_project(project_dir):
        # Vite dev server — handles TSX transpilation, HMR, everything
        subprocess.Popen(
            ["npx", "vite", "--port", str(port), "--host"],
            cwd=project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=shell,
        )
        log.info(f"Vite dev server on :{port} for {project_dir}")
        return f"http://localhost:{port}"

    elif _is_html_project(project_dir):
        # Static server for vanilla HTML
        subprocess.Popen(
            [_sys.executable, "-m", "http.server", str(port)],
            cwd=project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info(f"Static server on :{port} for {project_dir}")
        return f"http://localhost:{port}"

    else:
        return f"No serveable content in {project_dir}"
