"""QA tool — test a built app before shipping.

The wave calls this after writing an HTML file.
Runs static analysis + headless browser tests.
Reports errors the wave must fix before delivering.
"""

from __future__ import annotations

import logging
from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.tools.qa")


class Undertow(BaseTool):
    name = "undertow"
    description = (
        "Test an HTML file for errors before delivering. "
        "Checks: valid structure, JS syntax, console errors in headless browser, "
        "canvas rendering, visible content. Returns PASS or FAIL with error list. "
        "ALWAYS run this on code you built before calling message_result."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the HTML file to test"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kw) -> ToolResult:
        try:
            from ..undertow import run_drag, format_qa_report
            result = await run_drag(path)
            report = format_qa_report(result)
            return ToolResult(report, is_error=not result["passed"])
        except Exception as e:
            return ToolResult(f"QA error: {e}", is_error=True)
