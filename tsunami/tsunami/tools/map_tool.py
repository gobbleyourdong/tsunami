"""Map tool — parallel subtask spawning.

The general: divide and conquer at scale.
Spawns parallel subtasks for batch processing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from .base import BaseTool, ToolResult
from .shell import ShellExec

log = logging.getLogger("tsunami.map")


class MapTool(BaseTool):
    name = "map_parallel"
    description = (
        "Spawn parallel subtasks for batch processing. The general: divide and conquer. "
        "Provide a command template with {item} placeholder and a list of items. "
        "All commands run in parallel."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command_template": {
                    "type": "string",
                    "description": "Shell command with {item} placeholder (e.g. 'curl {item} > /tmp/{item}.html')",
                },
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of items to process",
                },
                "max_concurrent": {
                    "type": "integer",
                    "description": "Max parallel tasks",
                    "default": 5,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout per task in seconds",
                    "default": 60,
                },
            },
            "required": ["command_template", "items"],
        }

    async def execute(self, command_template: str, items: list[str],
                      max_concurrent: int = 5, timeout: int = 60, **kw) -> ToolResult:
        if not items:
            return ToolResult("No items to process.")

        if len(items) > 50:
            return ToolResult(f"Too many items ({len(items)}). Max 50 per batch.", is_error=True)

        semaphore = asyncio.Semaphore(max_concurrent)
        shell = ShellExec(self.config)
        results = {}

        async def run_one(item: str):
            async with semaphore:
                cmd = command_template.replace("{item}", item)
                result = await shell.execute(command=cmd, timeout=timeout)
                results[item] = {"output": result.content[:500], "error": result.is_error}

        tasks = [run_one(item) for item in items]
        await asyncio.gather(*tasks, return_exceptions=True)

        succeeded = sum(1 for r in results.values() if not r.get("error"))
        failed = len(results) - succeeded

        lines = [f"Processed {len(items)} items: {succeeded} succeeded, {failed} failed"]
        for item, res in results.items():
            status = "ERROR" if res["error"] else "OK"
            output = res["output"][:200]
            lines.append(f"  [{status}] {item}: {output}")

        return ToolResult("\n".join(lines))
