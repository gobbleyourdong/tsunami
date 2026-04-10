"""Session tools — list and summarize past sessions for resumption.

When a task dies mid-way, the agent can list past sessions and read
a summary of what was accomplished, then continue the work.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.session_tools")


class SessionList(BaseTool):
    """List recent agent sessions."""

    name = "session_list"
    description = (
        "List recent agent sessions. Shows session ID, iteration count, "
        "and completion status. Use to find a session to resume."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max sessions to show", "default": 5},
            },
        }

    async def execute(self, limit: int = 5, **kwargs) -> ToolResult:
        from ..session import list_sessions
        history_dir = Path(self.config.workspace_dir) / ".history"
        sessions = list_sessions(history_dir)[:limit]

        if not sessions:
            return ToolResult("No saved sessions found.")

        import datetime
        lines = []
        for s in sessions:
            ts = datetime.datetime.fromtimestamp(s["timestamp"]).strftime("%Y-%m-%d %H:%M")
            status = "✓ complete" if s["complete"] else f"○ stopped at iteration {s['iteration']}"
            lines.append(f"  {s['id']} | {ts} | {status}")

        return ToolResult(f"Recent sessions:\n" + "\n".join(lines))


class SessionSummary(BaseTool):
    """Get a summary of what a past session accomplished."""

    name = "session_summary"
    description = (
        "Read a past session and summarize what was accomplished. "
        "Returns the original task, tools called, files written, and last state. "
        "Use to understand what to resume."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID from session_list"},
            },
            "required": ["session_id"],
        }

    async def execute(self, session_id: str = "", **kwargs) -> ToolResult:
        if not session_id:
            return ToolResult("session_id required", is_error=True)

        path = Path(self.config.workspace_dir) / ".history" / f"{session_id}.jsonl"
        if not path.exists():
            return ToolResult(f"Session {session_id} not found", is_error=True)

        try:
            messages = []
            meta = {}
            with open(path) as f:
                for line in f:
                    record = json.loads(line.strip())
                    if record.get("_meta"):
                        meta = record
                    else:
                        messages.append(record)

            # Extract key info
            task = ""
            tools_used = []
            files_written = []
            errors = []

            for m in messages:
                if m["role"] == "user" and not task:
                    task = m["content"][:200]
                if m.get("tool_call"):
                    tc = m["tool_call"]
                    func = tc.get("function", tc)
                    name = func.get("name", "")
                    tools_used.append(name)
                    # Track file writes
                    args = func.get("arguments", {})
                    if name in ("file_write", "file_append") and "path" in args:
                        files_written.append(args["path"])
                if m["role"] == "tool_result" and "ERROR" in m.get("content", ""):
                    errors.append(m["content"][:100])

            summary = f"Session: {session_id}\n"
            summary += f"Iterations: {meta.get('iteration', '?')}\n"
            summary += f"Complete: {meta.get('task_complete', False)}\n"
            summary += f"Task: {task}\n"
            summary += f"Tools called ({len(tools_used)}): {', '.join(dict.fromkeys(tools_used))}\n"
            if files_written:
                summary += f"Files written: {', '.join(files_written[-10:])}\n"
            if errors:
                summary += f"Errors ({len(errors)}): {errors[-1]}\n"

            return ToolResult(summary)

        except Exception as e:
            return ToolResult(f"Error reading session: {e}", is_error=True)
