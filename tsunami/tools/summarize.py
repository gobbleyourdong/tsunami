"""File summarization via fast model — Manus recursive summarization pattern.

Instead of reading a large file into the 122B's limited context,
offload summarization to the fast 2B model. Returns a compressed
summary that fits in context without overflow.

This enables the "read 100 files" pattern: summarize each with 2B,
accumulate summaries in the 122B's context.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.summarize")


class SummarizeFile(BaseTool):
    """Summarize a file using the fast model."""

    name = "summarize_file"
    description = "Summarize a file via fast 2B model. Saves context. Use before file_read for large files."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to summarize"},
                "focus": {
                    "type": "string",
                    "description": "What to focus on in the summary (optional)",
                    "default": "",
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str = "", focus: str = "", **kwargs) -> ToolResult:
        if not path:
            return ToolResult("path is required", is_error=True)

        # Resolve path
        from .filesystem import _resolve_path
        p = _resolve_path(path, self.config.workspace_dir)
        if not p.exists():
            return ToolResult(f"File not found: {path}", is_error=True)

        try:
            text = p.read_text(errors="replace")
        except Exception as e:
            return ToolResult(f"Error reading {path}: {e}", is_error=True)

        # Truncate to ~6000 chars for the 2B's context
        if len(text) > 6000:
            text = text[:6000] + "\n... [truncated]"

        # Build prompt for the fast model
        focus_hint = f" Focus on: {focus}" if focus else ""
        prompt = f"""<|im_start|>system
Summarize the following file concisely. Extract key points, main arguments, important data, and conclusions.{focus_hint}
<|im_end|>
<|im_start|>user
File: {p.name}

{text}
<|im_end|>
<|im_start|>assistant
"""

        # Call the fast model (2B on port 8092)
        try:
            import httpx
            import os as _os
            _eddy = _os.environ.get("TSUNAMI_EDDY_ENDPOINT", "http://localhost:8092")
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{_eddy}/completion",
                    json={
                        "prompt": prompt,
                        "temperature": 0.3,
                        "n_predict": 1024,
                        "stop": ["<|im_end|>", "<|im_start|>"],
                    },
                )
                if resp.status_code != 200:
                    return ToolResult(f"Fast model error: {resp.status_code}", is_error=True)

                import re
                content = resp.json().get("content", "")
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

                if not content:
                    return ToolResult(f"Empty summary for {path}", is_error=True)

                return ToolResult(f"[Summary of {p.name} ({len(text)} chars)]\n{content}")

        except httpx.ConnectError:
            return ToolResult(
                "Fast model (2B) not running on port 8092. Falling back to file_read.",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(f"Summarization error: {e}", is_error=True)
