"""Closed-loop feedback — track what works, steer the next decision.

The agent measures quality (tension, compile, runtime) but discards it.
This module tracks tool outcomes within a session and injects guidance
based on what's actually working vs failing.

The feedback loop:
  tool call → outcome (success/fail/progress) → pattern detection → nudge
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger("tsunami.feedback")


@dataclass
class ToolOutcome:
    name: str
    success: bool
    made_progress: bool  # wrote a file, got useful results
    error: str = ""


class FeedbackTracker:
    """Track tool outcomes and generate steering advice."""

    def __init__(self):
        self.outcomes: list[ToolOutcome] = []
        self._last_nudge_iter = 0

    def record(self, tool_name: str, success: bool, made_progress: bool, error: str = ""):
        self.outcomes.append(ToolOutcome(
            name=tool_name, success=success,
            made_progress=made_progress, error=error,
        ))

    def get_nudge(self, iteration: int) -> str | None:
        """Disabled for zero-shot (2026-04-13). Nudges injected as system
        messages weren't being parsed by base Gemma-4 — they polluted context
        without shaping behavior. Skills (tsunami/skills/*/SKILL.md) carry
        the workflow guidance now. record() still runs for telemetry."""
        return None
        # Original logic preserved below for reference / re-enable via flag.
        # Only nudge every 5 iterations
        if iteration - self._last_nudge_iter < 5:
            return None
        if len(self.outcomes) < 5:
            return None

        recent = self.outcomes[-8:]
        self._last_nudge_iter = iteration

        # Pattern: repeated searches with no file writes → stop researching
        recent_names = [o.name for o in recent]
        searches = sum(1 for n in recent_names if n in ("search_web", "browser_navigate"))
        writes = sum(1 for n in recent_names if n in ("file_write", "file_edit"))
        if searches >= 4 and writes == 0:
            return (
                "FEEDBACK: You've searched 4+ times without writing code. "
                "You have enough context — start building now."
            )

        # Pattern: repeated file_read without file_write → stop reading, start writing
        reads = sum(1 for n in recent_names if n in ("file_read"))
        if reads >= 5 and writes == 0:
            return (
                "FEEDBACK: You've read 5+ files without writing anything. "
                "You have enough context — write code now."
            )

        # Pattern: compile errors recurring → try a different approach
        errors = [o for o in recent if not o.success]
        if len(errors) >= 3:
            error_tools = [o.name for o in errors]
            if error_tools.count("shell_exec") >= 2:
                return (
                    "FEEDBACK: Multiple command failures. Check your paths and "
                    "working directory. Use absolute paths if relative aren't working."
                )

        # Pattern: everything succeeding → positive reinforcement (don't change)
        successes = sum(1 for o in recent if o.success)
        progress = sum(1 for o in recent if o.made_progress)
        if successes >= 6 and progress >= 3:
            return None  # everything's working, don't interrupt

        # Pattern: writes succeeding but no compile check → remind to build
        if writes >= 3 and "shell_exec" not in recent_names[-3:]:
            return (
                "FEEDBACK: You've written 3+ files without running a build. "
                "Run shell_exec to compile (e.g. 'cd <project> && npm run build') "
                "so the typecheck catches missing imports / type errors before QA."
            )

        # Pattern: build-loop without source progress. QA-2 iter 11+12+14 all showed
        # the agent doing shell_exec (vite build) + undertow in a cycle with no
        # intervening file_write/file_edit, then exiting without ever calling
        # message_result. Re-running the build against unchanged source produces
        # the same output — the fix has to be in App.tsx.
        #
        # We count the CONSECUTIVE build/QA streak since the last write (any file
        # edit in the window breaks the streak), not a whole-window count —
        # iter 14's `file_write, shell×5` defeated the prior whole-window check
        # (writes=1 ≠ 0) even though the agent was clearly stuck on rebuilds.
        streak = 0
        for name in reversed(self.outcomes[-8:]):
            if name.name in ("file_write", "file_edit"):
                break  # last write ends the streak
            if name.name in ("shell_exec", "undertow"):
                streak += 1
        if streak >= 3:
            return (
                f"FEEDBACK: You've run {streak} builds / QA checks in a row since "
                f"your last file_write or file_edit. Re-running won't change the "
                f"output — the fix has to be in the source code. file_edit (or "
                f"file_write) the failing file now, then run the build and undertow "
                f"again. Don't call message_result until undertow passes — the "
                f"deliverable gate will refuse it."
            )

        return None

    def summary(self) -> dict:
        """Return stats for logging."""
        total = len(self.outcomes)
        if total == 0:
            return {"total": 0}
        success = sum(1 for o in self.outcomes if o.success)
        progress = sum(1 for o in self.outcomes if o.made_progress)
        return {
            "total": total,
            "success_rate": round(success / total, 2),
            "progress_rate": round(progress / total, 2),
        }
