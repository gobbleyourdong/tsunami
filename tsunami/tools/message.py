"""Message tools — how the agent speaks to humans.

Default to info. Use ask only when genuinely blocked.
Use result only when truly done. Every unnecessary ask
wastes the user's time.
"""

from __future__ import annotations

import asyncio
import sys

from .base import BaseTool, ToolResult


# Global callback for user input — set by the CLI runner
_input_callback = None
_last_displayed = None  # Track last displayed text to suppress duplicates


def set_input_callback(fn):
    global _input_callback
    _input_callback = fn


class MessageInfo(BaseTool):
    name = "message_info"
    description = "Acknowledge, update, or inform the user. No response needed. The heartbeat pulse."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Information to share with the user"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str = "", **kw) -> ToolResult:
        global _last_displayed
        if text:
            # Strip emojis — Windows console (cp1252) crashes on them
            clean = text.encode("ascii", errors="ignore").decode("ascii")
            print(f"\n  {clean}")
        _last_displayed = text
        return ToolResult("Message delivered.")


class MessageAsk(BaseTool):
    name = "message_ask"
    description = "Request input from the user. Only use when genuinely blocked. The pause."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Question to ask the user"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str, **kw) -> ToolResult:
        print(f"\n  \033[33m?\033[0m {text}")
        if _input_callback:
            response = await _input_callback(text)
        else:
            # Fallback: read from stdin
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: input("\n> "))
        return ToolResult(f"User response: {response}")


class MessageResult(BaseTool):
    name = "message_result"
    description = "Deliver final outcome and end the task. The exhale: the work is done."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Final result to deliver"},
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths to attach as deliverables",
                    "default": [],
                },
            },
            "required": [],
        }

    async def execute(self, text: str = "", attachments: list[str] | None = None, **kw) -> ToolResult:
        global _last_displayed
        # Don't re-display if message_info already showed this exact text
        if text != _last_displayed:
            clean = text.encode("ascii", errors="ignore").decode("ascii")
            print(f"\n  {clean}")
        if attachments:
            print(f"  \033[2m{', '.join(attachments)}\033[0m")
        _last_displayed = None
        return ToolResult(text)
