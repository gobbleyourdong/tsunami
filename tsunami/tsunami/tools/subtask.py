"""Subtask management — decompose complex tasks and track progress.

Lighter than sub-agent spawning but gives structured task tracking.
The agent creates subtasks, marks them done, and can see what's left.
State persists in a JSON file in the workspace.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.subtask")


def _tasks_file(workspace: str) -> Path:
    return Path(workspace) / ".tasks.json"


def _load_tasks(workspace: str) -> list[dict]:
    f = _tasks_file(workspace)
    if f.exists():
        return json.loads(f.read_text())
    return []


def _save_tasks(workspace: str, tasks: list[dict]):
    _tasks_file(workspace).write_text(json.dumps(tasks, indent=2))


class SubtaskCreate(BaseTool):
    """Create subtasks for a complex task."""

    name = "subtask_create"
    description = (
        "Break a complex task into numbered subtasks. "
        "Creates a tracked list that persists to disk. "
        "Use when a task has 3+ distinct steps."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of subtask descriptions",
                },
            },
            "required": ["subtasks"],
        }

    async def execute(self, subtasks: list = None, **kwargs) -> ToolResult:
        if not subtasks:
            return ToolResult("subtasks list required", is_error=True)

        tasks = [{"id": i + 1, "desc": s if isinstance(s, str) else str(s), "done": False}
                 for i, s in enumerate(subtasks)]
        _save_tasks(self.config.workspace_dir, tasks)

        lines = [f"  {'✓' if t['done'] else '○'} {t['id']}. {t['desc']}" for t in tasks]
        return ToolResult(f"Created {len(tasks)} subtasks:\n" + "\n".join(lines))


class SubtaskDone(BaseTool):
    """Mark a subtask as complete."""

    name = "subtask_done"
    description = "Mark a subtask as complete by ID number."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Subtask ID to mark done"},
            },
            "required": ["id"],
        }

    async def execute(self, id: int = 0, **kwargs) -> ToolResult:
        tasks = _load_tasks(self.config.workspace_dir)
        if not tasks:
            return ToolResult("No subtasks found", is_error=True)

        for t in tasks:
            if t["id"] == id:
                t["done"] = True
                _save_tasks(self.config.workspace_dir, tasks)
                done = sum(1 for t in tasks if t["done"])
                remaining = [t for t in tasks if not t["done"]]
                msg = f"✓ Subtask {id} done ({done}/{len(tasks)} complete)"
                if remaining:
                    msg += f"\nNext: {remaining[0]['id']}. {remaining[0]['desc']}"
                else:
                    msg += "\nAll subtasks complete! Deliver via message_result."
                return ToolResult(msg)

        return ToolResult(f"Subtask {id} not found", is_error=True)
