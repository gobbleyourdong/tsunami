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
            # and placeholder deliverables silently pass.
            if not expect:
                try:
                    from .filesystem import _session_task_prompt
                    expect = _session_task_prompt or ""
                except Exception:
                    pass
            # Resolve workspace-relative paths the same way file_write does.
            # Without this, undertow couldn't find dist/index.html when the
            # model wrote `path: "dist/index.html"` or `deliverables/.../...`
            # because it treated the arg as CWD-relative. Mirror file_write's
            # _resolve_path so paths the model can write are paths undertow
            # can read. (2026-04-13 zero-shot smoke fix.)
            from .filesystem import _resolve_path, _active_project
            from pathlib import Path as _P
            try:
                resolved = _resolve_path(path, self.config.workspace_dir, _active_project)
                if _P(resolved).exists():
                    path = str(resolved)
                elif _active_project:
                    # Path resolved but file doesn't exist — common failure
                    # mode: model passed a bare "dist/index.html" without the
                    # project prefix. Try prepending the active project.
                    # (Gallery test: "dist/index.html" should resolve to
                    # <ws>/<project>/dist/index.html, not <ws>/dist/index.html.)
                    base = _P(self.config.workspace_dir) / _active_project.lstrip("/")
                    candidate = (base / path.lstrip("/")).resolve()
                    if candidate.exists():
                        path = str(candidate)
                    else:
                        # Last resort: search for any matching path under
                        # deliverables/*/. Covers cases where _active_project
                        # wasn't set but a single project exists.
                        deliverables = _P(self.config.workspace_dir) / "deliverables"
                        if deliverables.exists():
                            for proj in deliverables.iterdir():
                                if not proj.is_dir(): continue
                                candidate2 = (proj / path.lstrip("/")).resolve()
                                if candidate2.exists():
                                    path = str(candidate2)
                                    break
            except Exception:
                pass
            from ..undertow import run_drag, format_qa_report
            # Re-derive the scaffold from the session's original user prompt
            # so the model-invoked undertow path gets the same direction-set
            # routing as the auto-QA path in agent.py. Cheap (one keyword
            # sweep); no extra state plumbing needed.
            scaffold = None
            try:
                from ..planfile import pick_scaffold
                from .filesystem import _session_task_prompt as _stp
                if _stp:
                    scaffold = pick_scaffold(_stp)
            except Exception:
                pass
            result = await run_drag(path, user_request=expect, scaffold=scaffold)
            report = format_qa_report(result)
            tension = result.get("code_tension", 0)
            failed = result.get("levers_failed", 0)
            total = result.get("levers_total", 0)
            report += f"\n\nCode tension: {tension:.2f} ({failed}/{total} levers failed)"
            return ToolResult(report, is_error=not result["passed"])
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            return ToolResult(f"QA error: {e!r}\n{tb[-800:]}", is_error=True)
