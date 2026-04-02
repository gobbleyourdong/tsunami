"""WebSocket bridge — streams agent activity to the desktop UI.

Listens on ws://localhost:3002. Sends real-time updates:
- tool_call: what tool is running, with file content for code view
- message: agent's text responses
- plan: phase updates
- complete: task done with iteration count
- error: something went wrong
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets

from tsunami.config import TsunamiConfig
from tsunami.agent import Agent
from tsunami.state import AgentState

log = logging.getLogger("tsunami.bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

PORT = 3002


class StreamingAgent(Agent):
    """Agent that streams tool calls to a WebSocket client."""

    def __init__(self, config, websocket):
        super().__init__(config)
        self._ws = websocket
        self._original_add_tool_result = self.state.add_tool_result

    async def _step(self, _watcher_depth=0):
        """Override to intercept tool calls and stream them."""
        result = await super()._step(_watcher_depth)

        # Stream the latest tool call to the UI
        if self.state.conversation:
            for msg in reversed(self.state.conversation[-3:]):
                # Find assistant messages with tool calls
                if msg.role == "assistant" and hasattr(msg, 'tool_call') and msg.tool_call:
                    tc = msg.tool_call.get("function", {})
                    name = tc.get("name", "")
                    args = tc.get("arguments", {})

                    payload = {
                        "type": "tool_call",
                        "name": name,
                        "preview": str(args)[:200],
                    }

                    # Include file content for code view
                    if name in ("file_write", "file_edit") and isinstance(args, dict):
                        payload["path"] = args.get("path", "")
                        payload["content"] = args.get("content", "")[:5000]

                    try:
                        await self._ws.send(json.dumps(payload))
                    except Exception:
                        pass
                    break

                # Find tool results
                if msg.role == "tool_result":
                    break

        return result


async def handle_client(websocket):
    """Handle a single WebSocket client connection."""
    log.info("Client connected")

    config = TsunamiConfig.from_yaml("config.yaml")
    config.max_iterations = 60

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "text": "Invalid JSON"}))
                continue

            if msg.get("type") == "prompt":
                text = msg.get("text", "").strip()
                if not text:
                    continue

                log.info(f"Prompt: {text[:100]}")
                await websocket.send(json.dumps({"type": "message", "text": f"Building: {text}"}))

                try:
                    agent = StreamingAgent(config, websocket)
                    result = await agent.run(text)
                    await websocket.send(json.dumps({
                        "type": "complete",
                        "text": result[:1000],
                        "iterations": agent.state.iteration,
                    }))
                except Exception as e:
                    log.error(f"Agent error: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "text": f"Agent error: {e}",
                    }))

    except websockets.exceptions.ConnectionClosed:
        log.info("Client disconnected")


async def main():
    log.info(f"WebSocket bridge on ws://localhost:{PORT}")
    async with websockets.serve(handle_client, "localhost", PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
