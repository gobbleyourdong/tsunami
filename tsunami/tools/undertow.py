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
        "Test an HTML file by pulling levers — screenshot, keypresses, clicks, "
        "text reads. Reports what it sees. PASS or FAIL with specifics. "
        "Provide 'expect' to describe what the app should look like/do. "
        "ALWAYS run this on code you built before calling message_result."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the HTML file to test"},
                "expect": {"type": "string", "description": "What the app should look like and do — the undertow compares this against what it sees"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, expect: str = "", **kw) -> ToolResult:
        try:
            # Fallback: if the model didn't pass expect, use the session's
            # original user prompt. Without this, undertow with no expect
            # runs only a 2-lever plan (console + screenshot, no compare)
            # and placeholder deliverables silently pass. This is the same
            # module-global pattern filesystem.py uses for exfil checks;
            # it's a hack but an existing consistent one.
            if not expect:
                try:
                    from .filesystem import _session_task_prompt
                    expect = _session_task_prompt or ""
                except Exception:
                    pass
            from ..undertow import run_drag, format_qa_report
            result = await run_drag(path, user_request=expect)
            report = format_qa_report(result)
            tension = result.get("code_tension", 0)
            failed = result.get("levers_failed", 0)
            total = result.get("levers_total", 0)
            report += f"\n\nCode tension: {tension:.2f} ({failed}/{total} levers failed)"
            return ToolResult(report, is_error=not result["passed"])
        except Exception as e:
            return ToolResult(f"QA error: {e}", is_error=True)
