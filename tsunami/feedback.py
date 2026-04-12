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
        """Analyze recent outcomes and return steering advice, or None."""
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
        reads = sum(1 for n in recent_names if n in ("file_read", "match_glob", "match_grep"))
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
                "FEEDBACK: You've written 3+ files. Run 'npm run build' "
                "(NOT 'npx vite build') so the typecheck gate runs and catches "
                "missing imports / type errors."
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
