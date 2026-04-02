"""Persistent Python interpreter — CodeAct paradigm.

Instead of fixed tool calls, the agent writes executable Python code.
The interpreter persists across calls — variables, imports, and state
survive. This collapses 5-10 sequential tool calls into 1.

This is the single most impactful Manus feature.
"""

from __future__ import annotations

import asyncio
import io
import logging
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.python_exec")

# Persistent namespace shared across calls
_namespace = {}


class PythonExec(BaseTool):
    """Execute Python code in a persistent interpreter."""

    name = "python_exec"
    description = "Run Python code in a persistent interpreter. State survives across calls. print() for output."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Use print() for output.",
                },
            },
            "required": ["code"],
        }

    async def execute(self, code: str = "", **kwargs) -> ToolResult:
        if not code.strip():
            return ToolResult("No code provided", is_error=True)

        # Safety: block obviously destructive operations
        blocked = ["shutil.rmtree", "os.remove", "os.unlink", "subprocess.call('rm"]
        for b in blocked:
            if b in code:
                return ToolResult(f"BLOCKED: {b} is not allowed in python_exec", is_error=True)

        # Capture stdout/stderr
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        # Inject useful defaults into namespace (persistent across calls)
        if "os" not in _namespace:
            import os, json, csv, re, math, datetime, collections

            _namespace["os"] = os
            _namespace["json"] = json
            _namespace["csv"] = csv
            _namespace["re"] = re
            _namespace["math"] = math
            _namespace["datetime"] = datetime
            _namespace["collections"] = collections
            _namespace["Path"] = Path
            _namespace["__builtins__"] = __builtins__

        try:
            import os

            workspace_dir = str(Path(self.config.workspace_dir).resolve())
            ark_dir = str(Path(workspace_dir).parent.resolve())
            os.chdir(ark_dir)
            _namespace["ARK_DIR"] = ark_dir
            _namespace["WORKSPACE"] = workspace_dir
            _namespace["DELIVERABLES"] = str(Path(workspace_dir) / "deliverables")

            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                # Use exec for statements, eval for expressions
                try:
                    # Try eval first (single expression)
                    result = eval(code, _namespace)
                    if result is not None:
                        print(repr(result), file=stdout_buf)
                except SyntaxError:
                    # Fall back to exec (multiple statements)
                    exec(code, _namespace)

            stdout = stdout_buf.getvalue().strip()
            stderr = stderr_buf.getvalue().strip()

            output = stdout
            if stderr:
                output += f"\n[stderr] {stderr}" if output else f"[stderr] {stderr}"

            if not output:
                output = "(no output — code executed successfully)"

            # Truncate massive output
            if len(output) > 8000:
                output = output[:8000] + "\n... [TRUNCATED]"

            return ToolResult(output)

        except Exception as e:
            tb = traceback.format_exc()
            # Keep last 500 chars of traceback
            if len(tb) > 500:
                tb = "..." + tb[-500:]
            return ToolResult(f"Error: {e}\n{tb}", is_error=True)
