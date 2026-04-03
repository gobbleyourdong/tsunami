"""Persistent serve daemon — like ComfyUI on :8188.

Starts once, stays alive, auto-detects the latest deliverable
and serves it. When a new project gets built, it hot-swaps to that.

Run standalone:
    python -m tsunami.serve_daemon

Or import and call start_daemon() from the launcher.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("tsunami.serve_daemon")

SERVE_PORT = int(os.environ.get("TSUNAMI_SERVE_PORT", "9876"))
WORKSPACE = os.environ.get("TSUNAMI_WORKSPACE", "./workspace")


def find_latest_project(workspace: str = WORKSPACE) -> Path | None:
    """Find the most recently modified project in deliverables/."""
    deliverables = Path(workspace) / "deliverables"
    if not deliverables.exists():
        return None
    latest = None
    latest_time = 0
    for d in deliverables.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            try:
                mtime = max(
                    (f.stat().st_mtime for f in d.rglob("*")
                     if f.is_file() and "node_modules" not in str(f)),
                    default=0,
                )
                if mtime > latest_time:
                    latest_time = mtime
                    latest = d
            except Exception:
                pass
    return latest


def _kill_port(port: int):
    """Kill whatever is listening on this port (cross-platform)."""
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


def _is_vite_project(project_dir: Path) -> bool:
    """Does this project have a package.json with vite?"""
    pkg = project_dir / "package.json"
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        return "vite" in deps
    except Exception:
        return False


def serve(project_dir: Path, port: int = SERVE_PORT) -> subprocess.Popen | None:
    """Serve a project. Returns the server process."""
    _kill_port(port)
    time.sleep(0.3)

    shell = sys.platform == "win32"
    if _is_vite_project(project_dir):
        # Install deps if needed — check vite CLI actually exists, not just node_modules dir
        vite_cli = project_dir / "node_modules" / ".bin" / ("vite.cmd" if sys.platform == "win32" else "vite")
        if not vite_cli.exists():
            log.info(f"Installing deps for {project_dir.name} (vite CLI missing)")
            subprocess.run(
                ["npm", "install", "--no-audit", "--no-fund"],
                cwd=str(project_dir), capture_output=True, timeout=60,
                shell=shell,
            )
        proc = subprocess.Popen(
            ["npx", "vite", "--port", str(port), "--host"],
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            shell=shell,
        )
        log.info(f"Vite dev server on :{port} for {project_dir.name}")
        return proc
    elif (project_dir / "index.html").exists():
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port)],
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        log.info(f"Static server on :{port} for {project_dir.name}")
        return proc
    return None


def run_daemon(workspace: str = WORKSPACE, port: int = SERVE_PORT):
    """Run the serve daemon — polls for new projects, auto-swaps.

    Like ComfyUI: start once, leave running, always serving the latest.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"Tsunami serve daemon on :{port}")
    print(f"Watching: {workspace}/deliverables/")
    print(f"Open http://localhost:{port} to see the latest build\n")

    current_project = None
    server_proc = None

    try:
        while True:
            latest = find_latest_project(workspace)
            if latest and str(latest) != current_project:
                log.info(f"New project detected: {latest.name}")
                current_project = str(latest)
                if server_proc:
                    server_proc.terminate()
                    try:
                        server_proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        server_proc.kill()
                server_proc = serve(latest, port)
                if server_proc:
                    print(f"  -> http://localhost:{port}  ({latest.name})")

            # Check if server is still alive
            if server_proc and server_proc.poll() is not None:
                log.warning(f"Server died, restarting for {current_project}")
                latest = Path(current_project) if current_project else None
                if latest and latest.exists():
                    server_proc = serve(latest, port)

            time.sleep(3)

    except KeyboardInterrupt:
        print("\nShutting down serve daemon")
        if server_proc:
            server_proc.terminate()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tsunami Serve Daemon")
    parser.add_argument("--port", type=int, default=SERVE_PORT)
    parser.add_argument("--workspace", type=str, default=WORKSPACE)
    args = parser.parse_args()
    run_daemon(args.workspace, args.port)
