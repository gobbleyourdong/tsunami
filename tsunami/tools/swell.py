"""Swell tool — wave dispatches tool-wielding eddy workers.

The wave (27B) breaks a task into subtasks and sends each to a
eddy (2B) that has its own agent loop with file_read, shell_exec,
match_grep, and a 'done' tool to report results.

Eddies run in parallel. Results merge back to the wave.
"""

from __future__ import annotations

import asyncio
import logging
import os

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.swell")

MAX_WORKERS = int(os.environ.get("TSUNAMI_MAX_WORKERS", "4"))


class Swell(BaseTool):
    """Dispatch parallel eddy workers for batch tasks."""

    name = "swell"
    description = (
        f"Dispatch up to {MAX_WORKERS} parallel eddy workers for batch tasks. "
        "Each eddy has its own agent loop with tools (file_read, shell_exec, match_grep). "
        "Give each eddy a specific subtask. Eddies run simultaneously and report back. "
        "Use for: reading many files, parallel searches, batch processing."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": f"List of subtask prompts (max {MAX_WORKERS}). Each runs on a eddy worker.",
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt for all eddies (default: focused worker)",
                    "default": "",
                },
            },
            "required": ["tasks"],
        }

    async def execute(self, tasks: list = None, system_prompt: str = "", **kwargs) -> ToolResult:
        if not tasks:
            return ToolResult("tasks list required", is_error=True)

        tasks = tasks[:MAX_WORKERS]
        log.info(f"Swarming {len(tasks)} eddies")

        from ..eddy import run_swarm, format_swarm_results

        # Use the ark project root as workdir so eddies can access files
        workdir = str(self.config.workspace_dir)
        # Go up one level to project root (workspace is inside ark)
        import os.path
        project_root = os.path.dirname(os.path.abspath(workdir))

        results = await run_swarm(
            tasks=tasks,
            workdir=project_root,
            max_concurrent=MAX_WORKERS,
            system_prompt=system_prompt,
        )

        return ToolResult(format_swarm_results(results))
