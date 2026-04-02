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
import os
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import re

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.python_exec")

# Persistent namespace shared across calls
_namespace = {}


def _execution_cwd() -> str:
    """Use the active project root when available, otherwise fall back to repo root."""
    try:
        from .plan import get_agent_state
        state = get_agent_state()
        root = getattr(state, "active_project_root", "") if state is not None else ""
        if root and os.path.isdir(root):
            return root
    except Exception:
        pass
    return str(Path(__file__).parent.parent.parent)


def _normalize_project_prefixed_code(code: str, exec_cwd: str) -> str:
    """Rewrite workspace-prefixed paths to project-local paths when already inside a project.

    The model often emits paths like ./workspace/deliverables/<project>/src/App.tsx
    even though python_exec runs from that project's root. Inside the active project,
    those paths should become ./src/App.tsx.
    """
    try:
        project_root = Path(exec_cwd).resolve()
        from .plan import get_agent_state
        state = get_agent_state()
        active_project = getattr(state, "active_project", "") if state is not None else ""
    except Exception:
        return code

    if not active_project:
        return code

    prefixes = [
        f"./workspace/deliverables/{active_project}/",
        f"workspace/deliverables/{active_project}/",
        f"/workspace/deliverables/{active_project}/",
        f"{project_root.as_posix()}/",
    ]

    normalized = code
    for prefix in prefixes:
        normalized = normalized.replace(prefix, "./")

    normalized = re.sub(
        r"(?<![\w/])(?:\.?/)?workspace/deliverables/[^/\s'\"`]+/",
        "./",
        normalized,
    )
    normalized = re.sub(
        r"(?<![\w.])/workspace/deliverables/[^/\s'\"`]+/",
        "./",
        normalized,
    )

    repo_root = Path(__file__).parent.parent.parent.resolve().as_posix()
    normalized = re.sub(r"(?<![\w/])\./tsunami/", f"{repo_root}/tsunami/", normalized)
    normalized = re.sub(r"(?<![\w/])tsunami/", f"{repo_root}/tsunami/", normalized)
    normalized = re.sub(r"(?<![\w/])\./toolboxes/", f"{repo_root}/toolboxes/", normalized)
    normalized = re.sub(r"(?<![\w/])toolboxes/", f"{repo_root}/toolboxes/", normalized)
    normalized = re.sub(r"(?<![\w/])\./README\.md", f"{repo_root}/README.md", normalized)
    normalized = re.sub(r"(?<![\w/])README\.md", f"{repo_root}/README.md", normalized)
    return normalized


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
            import json, csv, re, math, datetime, collections

            _namespace["os"] = os
            _namespace["json"] = json
            _namespace["csv"] = csv
            _namespace["re"] = re
            _namespace["math"] = math
            _namespace["datetime"] = datetime
            _namespace["collections"] = collections
            _namespace["Path"] = Path
            _namespace["__builtins__"] = __builtins__

        ark_dir = str(Path(__file__).parent.parent.parent)
        exec_cwd = _execution_cwd()
        code = _normalize_project_prefixed_code(code, exec_cwd)
        prev_cwd = os.getcwd()
        os.chdir(exec_cwd)
        _namespace["ARK_DIR"] = ark_dir
        _namespace["WORKSPACE"] = os.path.join(ark_dir, "workspace")
        _namespace["DELIVERABLES"] = os.path.join(ark_dir, "workspace", "deliverables")
        _namespace["CWD"] = exec_cwd
        _namespace["PROJECT_ROOT"] = exec_cwd

        try:
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
        finally:
            try:
                os.chdir(prev_cwd)
            except Exception:
                pass
