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


def scan_files():
    """Scan deliverables for all source files with mtimes."""
    files = {}
    if not WATCH_DIR.exists():
        return files
    for f in WATCH_DIR.rglob("*"):
        if f.is_file() and not any(s in f.parts for s in SKIP):
            rel = str(f.relative_to(WATCH_DIR))
            try:
                files[rel] = f.stat().st_mtime
            except OSError:
                pass
    return files


def read_file(rel_path):
    """Read file content (text only, skip binary)."""
    full = WATCH_DIR / rel_path
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
        await asyncio.sleep(1)

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
    await websocket.send(json.dumps({
        "type": "files",
        "files": sorted(current.keys()),
    }))
    try:
        async for _ in websocket:
            pass  # we only send, never receive
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
