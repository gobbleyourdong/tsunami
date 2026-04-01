"""File matching tools — glob and grep.

The compass and the metal detector.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult


class MatchGlob(BaseTool):
    name = "match_glob"
    description = "Find files by name and path patterns. The compass: locate what you need."
    concurrent_safe = True

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py', 'src/**/*.ts')"},
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "limit": {"type": "integer", "description": "Max results", "default": 50},
            },
            "required": ["pattern"],
        }

    async def execute(self, pattern: str, directory: str = ".", limit: int = 50, **kw) -> ToolResult:
        try:
            root = Path(directory).expanduser().resolve()
            if not root.exists():
                return ToolResult(f"Directory not found: {directory}", is_error=True)

            matches = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            results = [str(m.relative_to(root)) for m in matches[:limit]]
            total = len(matches)

            if not results:
                return ToolResult(f"No files match '{pattern}' in {root}")

            header = f"Found {total} files matching '{pattern}'"
            if total > limit:
                header += f" (showing first {limit})"

            if total > 20:
                header += f"\n⚡ {total} files found. Use python_exec to batch-read them or swell to process in parallel."

            return ToolResult(header + "\n" + "\n".join(results))
        except Exception as e:
            return ToolResult(f"Error globbing: {e}", is_error=True)


class MatchGrep(BaseTool):
    name = "match_grep"
    description = "Search file contents by regex pattern. The metal detector: find signal buried in noise."
    concurrent_safe = True

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "file_pattern": {"type": "string", "description": "Glob filter for files (e.g. '*.py')", "default": ""},
                "limit": {"type": "integer", "description": "Max results", "default": 30},
            },
            "required": ["pattern"],
        }

    async def execute(self, pattern: str, directory: str = ".", file_pattern: str = "",
                      limit: int = 30, **kw) -> ToolResult:
        try:
            root = Path(directory).expanduser().resolve()
            cmd = ["grep", "-rn", "--include", file_pattern or "*", "-E", pattern, str(root)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            lines = result.stdout.strip().splitlines()
            if not lines:
                return ToolResult(f"No matches for '{pattern}' in {root}")

            total = len(lines)
            selected = lines[:limit]
            header = f"Found {total} matches for '{pattern}'"
            if total > limit:
                header += f" (showing first {limit})"
            return ToolResult(header + "\n" + "\n".join(selected))
        except subprocess.TimeoutExpired:
            return ToolResult("Grep timed out after 30s", is_error=True)
        except Exception as e:
            return ToolResult(f"Error grepping: {e}", is_error=True)
