"""WebSocket bridge — connects the desktop UI to the Tsunami agent.

Listens on ws://localhost:3002. Each connection gets its own agent session.
UI sends: { type: "prompt", text: "build a calculator" }
Bridge sends back: tool calls, messages, completion status.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add tsunami to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets

from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

log = logging.getLogger("tsunami.bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

PORT = 3002


async def handle_client(websocket):
    """Handle a single WebSocket client connection."""
    log.info(f"Client connected")

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

                # Run agent
                try:
                    agent = Agent(config)
                    result = await agent.run(text)
                    await websocket.send(json.dumps({
                        "type": "complete",
                        "text": result[:1000],
                        "iterations": agent.state.iteration,
                    }))
                except Exception as e:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "text": f"Agent error: {e}",
                    }))

    except websockets.exceptions.ConnectionClosed:
        log.info("Client disconnected")


async def main():
    log.info(f"WebSocket bridge on ws://localhost:{PORT}")
    async with websockets.serve(handle_client, "localhost", PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
