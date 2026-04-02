"""WebSocket bridge — streams agent activity to the desktop UI in real time.

Hooks into the agent's state to intercept every tool call, tool result,
and message as it happens. Sends to the UI immediately.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets

from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

log = logging.getLogger("tsunami.bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

PORT = 3002

# Global state — all connected clients see everything
clients = set()
message_buffer = []  # last 100 messages for reconnecting clients
MAX_BUFFER = 100


async def broadcast(data):
    """Send to ALL connected clients."""
    msg = json.dumps(data)
    message_buffer.append(msg)
    if len(message_buffer) > MAX_BUFFER:
        message_buffer.pop(0)
    for ws in list(clients):
        try:
            await ws.send(msg)
        except Exception:
            clients.discard(ws)


def wire_streaming(agent, websocket, loop):
    """Monkey-patch the agent's state to stream everything to the UI."""
    state = agent.state

    # Intercept assistant messages (tool calls)
    original_add_assistant = state.add_assistant
    def streaming_add_assistant(content, tool_call=None):
        original_add_assistant(content, tool_call)
        if tool_call:
            func = tool_call.get("function", {})
            name = func.get("name", "")
            args = func.get("arguments", {})

            payload = {
                "type": "tool_call",
                "name": name,
                "preview": "",
            }

            if isinstance(args, dict):
                # For file writes, send content to code view
                if name in ("file_write", "file_edit", "file_append"):
                    payload["path"] = args.get("path", "")
                    payload["content"] = args.get("content", "")[:8000]
                    payload["preview"] = args.get("path", "")
                elif name == "shell_exec":
                    payload["preview"] = args.get("command", "")[:200]
                elif name == "search_web":
                    payload["preview"] = args.get("query", "")[:200]
                elif name == "project_init":
                    payload["preview"] = args.get("name", "")
                elif name == "swell":
                    tasks = args.get("tasks", [])
                    payload["preview"] = f"{len(tasks)} parallel tasks"
                elif name in ("message_info", "message_ask", "message_result"):
                    text = args.get("text", "")[:500]
                    payload = {"type": "message", "text": text}
                else:
                    payload["preview"] = str(args)[:200]

            asyncio.run_coroutine_threadsafe(broadcast(payload), loop)

    state.add_assistant = streaming_add_assistant

    # Intercept tool results
    original_add_tool_result = state.add_tool_result
    def streaming_add_tool_result(name, args, content, is_error=False):
        original_add_tool_result(name, args, content, is_error)

        # Send file list updates after file operations
        if name in ("file_write", "file_edit", "file_append", "project_init"):
            files = _scan_project_files(agent)
            if files:
                asyncio.run_coroutine_threadsafe(
                    _send(websocket, {"type": "files", "files": files}), loop
                )

        # Send tool result preview
        preview = content[:300] if isinstance(content, str) else str(content)[:300]
        payload = {
            "type": "tool_result",
            "name": name,
            "preview": preview,
            "is_error": is_error,
        }
        asyncio.run_coroutine_threadsafe(broadcast(payload), loop)

    state.add_tool_result = streaming_add_tool_result


def _scan_project_files(agent):
    """Scan the active deliverable for files."""
    deliverables = Path(agent.config.workspace_dir) / "deliverables"
    if not deliverables.exists():
        return []

    files = []
    for project in deliverables.iterdir():
        if not project.is_dir() or project.name.startswith("."):
            continue
        for f in sorted(project.rglob("*")):
            if f.is_file() and "node_modules" not in str(f) and "dist" not in str(f) and ".vite" not in str(f):
                rel = str(f.relative_to(deliverables))
                files.append(rel)
    return files[:100]  # cap at 100


async def _send(ws, data):
    """Safe send — ignore if connection closed."""
    try:
        await ws.send(json.dumps(data))
    except Exception:
        pass


async def handle_client(websocket):
    """Handle a single WebSocket client connection."""
    log.info("Client connected")
    clients.add(websocket)

    # Replay buffered messages so reconnecting clients catch up
    for msg in message_buffer:
        try:
            await websocket.send(msg)
        except Exception:
            break

    config = TsunamiConfig.from_yaml("config.yaml")
    config.max_iterations = 60
    loop = asyncio.get_event_loop()

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await broadcast( {"type": "error", "text": "Invalid JSON"})
                continue

            if msg.get("type") == "prompt":
                text = msg.get("text", "").strip()
                if not text:
                    continue

                log.info(f"Prompt: {text[:100]}")
                await broadcast( {"type": "message", "text": f"Building: {text}"})

                try:
                    agent = Agent(config)
                    wire_streaming(agent, websocket, loop)

                    result = await agent.run(text)
                    await broadcast( {
                        "type": "complete",
                        "text": result[:1000],
                        "iterations": agent.state.iteration,
                    })

                    # Send final file list
                    files = _scan_project_files(agent)
                    if files:
                        await broadcast( {"type": "files", "files": files})

                except Exception as e:
                    log.error(f"Agent error: {e}", exc_info=True)
                    await broadcast( {"type": "error", "text": str(e)})

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        log.info("Client disconnected")


async def main():
    log.info(f"WebSocket bridge on ws://localhost:{PORT}")
    async with websockets.serve(handle_client, "localhost", PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
