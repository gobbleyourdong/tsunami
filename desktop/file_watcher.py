"""File watcher — watches deliverables/ and pushes changes to the UI via WebSocket.

Runs alongside the bridge. Scans every second for new/modified files.
Sends file list + file content to the UI so the code view updates in real time.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets

PORT = 3003  # separate port from the agent bridge
WATCH_DIR = Path(__file__).parent.parent / "workspace" / "deliverables"
SKIP = {"node_modules", "dist", ".vite", "__pycache__", ".git"}

clients = set()
file_states = {}  # path → mtime


def find_latest_project():
    """Find the most recently modified project in deliverables/."""
    if not WATCH_DIR.exists():
        return None
    latest = None
    latest_time = 0
    for d in WATCH_DIR.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            try:
                mtime = max((f.stat().st_mtime for f in d.rglob("*") if f.is_file()), default=0)
                if mtime > latest_time:
                    latest_time = mtime
                    latest = d
            except Exception:
                pass
    return latest


def scan_files():
    """Scan the latest project for source files with mtimes."""
    files = {}
    project = find_latest_project()
    if not project:
        return files
    for f in project.rglob("*"):
        if f.is_file() and not any(s in f.parts for s in SKIP):
            rel = str(f.relative_to(project))
            try:
                files[rel] = f.stat().st_mtime
            except OSError:
                pass
    return files


def read_file(rel_path):
    """Read file content (text only, skip binary)."""
    project = find_latest_project()
    if not project:
        return "[no project]"
    full = project / rel_path
    try:
        if full.stat().st_size > 100_000:
            return f"[file too large: {full.stat().st_size // 1024}KB]"
        content = full.read_text(errors="replace")
        return content[:10000]
    except Exception:
        return "[unreadable]"


async def broadcast(data):
    """Send to all connected UI clients."""
    msg = json.dumps(data)
    for ws in list(clients):
        try:
            await ws.send(msg)
        except Exception:
            clients.discard(ws)


async def watcher_loop():
    """Poll filesystem every second, push changes."""
    global file_states

    while True:
        await asyncio.sleep(3)

        current = scan_files()

        # Find new or modified files
        changed = []
        for path, mtime in current.items():
            if path not in file_states or file_states[path] < mtime:
                changed.append(path)

        # Find deleted files
        deleted = [p for p in file_states if p not in current]

        if changed or deleted:
            # Send file list update
            file_list = sorted(current.keys())
            await broadcast({
                "type": "files",
                "files": file_list,
            })

            # Send content of changed files
            for path in changed:
                ext = path.rsplit(".", 1)[-1] if "." in path else ""
                if ext in ("tsx", "ts", "jsx", "js", "css", "html", "json", "md", "py", "txt"):
                    content = read_file(path)
                    await broadcast({
                        "type": "file_changed",
                        "path": path,
                        "content": content,
                    })

            file_states = current


async def handle_client(websocket):
    """New UI client connects — send current file list."""
    clients.add(websocket)
    current = scan_files()
    file_list = sorted(current.keys())
    await websocket.send(json.dumps({
        "type": "files",
        "files": file_list,
    }))
    # Send the most recently modified source file's content
    if file_list:
        code_exts = {"tsx", "ts", "jsx", "js", "css", "html", "json", "py"}
        source_files = [f for f in file_list if f.rsplit(".", 1)[-1] in code_exts]
        if source_files:
            # Find most recently modified
            newest = max(source_files, key=lambda f: current.get(f, 0))
            content = read_file(newest)
            await websocket.send(json.dumps({
                "type": "file_changed",
                "path": newest,
                "content": content,
            }))
    try:
        async for msg in websocket:
            # Handle file read requests from the UI
            try:
                data = json.loads(msg)
                if data.get("type") == "read" and data.get("path"):
                    content = read_file(data["path"])
                    await websocket.send(json.dumps({
                        "type": "file_changed",
                        "path": data["path"],
                        "content": content,
                    }))
            except (json.JSONDecodeError, Exception):
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)


async def main():
    print(f"File watcher on ws://localhost:{PORT}, watching {WATCH_DIR}")
    server = await websockets.serve(handle_client, "localhost", PORT)
    await watcher_loop()


if __name__ == "__main__":
    asyncio.run(main())
