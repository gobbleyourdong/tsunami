"""Dynamic tool filtering — steer tool selection based on recent effectiveness.

After each tool call, records (tool, tension_delta, success). Tracks a rolling
window and generates TOOL GUIDANCE notes before the next selection.

Phase detection:
- RESEARCH: >60% of recent tools are search/read
- BUILD: >60% of recent tools are write/edit
- VERIFY: recent tools are shell_exec (build commands)

Guidance injection:
- Lists recently effective vs ineffective tools
- Detects research loops ("SWITCH TO BUILDING")
- Detects good build momentum ("KEEP BUILDING")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger("tsunami.dynamic_tool_filter")

WINDOW_SIZE = 10

# Tool categories
RESEARCH_TOOLS = frozenset({"search_web", "file_read", "match_glob", "match_grep", "browser_navigate"})
BUILD_TOOLS = frozenset({"file_write", "file_edit", "project_init", "generate_image"})
VERIFY_TOOLS = frozenset({"shell_exec"})
DELIVER_TOOLS = frozenset({"message_result"})


@dataclass
class ToolRecord:
    """One tool call with its impact."""
    name: str
    tension_before: float
    tension_after: float
    success: bool

    @property
    def tension_delta(self) -> float:
        """Positive = tension went down (good). Negative = tension went up (bad)."""
        return self.tension_before - self.tension_after


class DynamicToolFilter:
    """Track tool effectiveness and generate guidance."""

    def __init__(self, window_size: int = WINDOW_SIZE):
        self.records: list[ToolRecord] = []
        self.window_size = window_size
        self._pending_tension: float | None = None

    def record_before(self, tension: float):
        """Record tension before a tool call."""
        self._pending_tension = tension

    def record_after(self, tool_name: str, tension_after: float, success: bool):
        """Record tool call result and tension after."""
        tension_before = self._pending_tension if self._pending_tension is not None else tension_after
        self.records.append(ToolRecord(
            name=tool_name,
            tension_before=tension_before,
            tension_after=tension_after,
            success=success,
        ))
        self._pending_tension = None
        # Trim
        if len(self.records) > self.window_size * 3:
            self.records = self.records[-self.window_size * 2:]

    def _recent(self) -> list[ToolRecord]:
        return self.records[-self.window_size:]

    def detect_phase(self) -> str:
        """Detect current phase based on recent tool usage."""
        recent = self._recent()
        if len(recent) < 3:
            return "UNKNOWN"

        names = [r.name for r in recent]
        total = len(names)

        research_count = sum(1 for n in names if n in RESEARCH_TOOLS)
        build_count = sum(1 for n in names if n in BUILD_TOOLS)
        verify_count = sum(1 for n in names if n in VERIFY_TOOLS)

        if research_count / total > 0.6:
            return "RESEARCH"
        if build_count / total > 0.6:
            return "BUILD"
        if verify_count / total > 0.4:
            return "VERIFY"
        if any(n in DELIVER_TOOLS for n in names[-2:]):
            return "DELIVER"
        return "MIXED"

    def get_guidance(self) -> str | None:
        """Generate tool guidance based on recent patterns.

        Returns a guidance note or None if no guidance needed.
        """
        recent = self._recent()
        if len(recent) < 5:
            return None

        phase = self.detect_phase()
        names = [r.name for r in recent]

        # Compute per-tool effectiveness
        tool_scores: dict[str, list[float]] = {}
        for r in recent:
            if r.name not in tool_scores:
                tool_scores[r.name] = []
            # Score: tension_delta (positive = good) + success bonus
            score = r.tension_delta + (0.1 if r.success else -0.1)
            tool_scores[r.name].append(score)

        # Average scores
        avg_scores = {name: sum(scores) / len(scores)
                      for name, scores in tool_scores.items()}

        # Sort by effectiveness
        ranked = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
        effective = [(n, s) for n, s in ranked if s > 0][:3]
        ineffective = [(n, s) for n, s in ranked if s < -0.05][:3]

        lines = []

        # Phase-based guidance
        if phase == "RESEARCH":
            research_count = sum(1 for n in names if n in RESEARCH_TOOLS)
            if research_count >= 6:
                lines.append("SWITCH TO BUILDING — you've researched enough, start writing code.")
        elif phase == "BUILD":
            build_count = sum(1 for n in names if n in BUILD_TOOLS)
            successes = sum(1 for r in recent if r.success and r.name in BUILD_TOOLS)
            if build_count >= 8 and successes >= 6:
                lines.append("GOOD MOMENTUM — keep building, your writes are succeeding.")

        # Tool effectiveness hints
        if effective:
            eff_str = ", ".join(f"{n} (+{s:.2f})" for n, s in effective)
            lines.append(f"Recently effective: {eff_str}")
        if ineffective:
            ineff_str = ", ".join(f"{n} ({s:.2f})" for n, s in ineffective)
            lines.append(f"Recently ineffective: {ineff_str}")

        if not lines:
            return None

        return "[TOOL GUIDANCE]\n" + "\n".join(lines)

    def summary(self) -> dict:
        """Stats for logging."""
        recent = self._recent()
        if not recent:
            return {"total": 0}
        success_rate = sum(1 for r in recent if r.success) / len(recent)
        avg_delta = sum(r.tension_delta for r in recent) / len(recent)
        return {
            "total": len(self.records),
            "recent": len(recent),
            "phase": self.detect_phase(),
            "success_rate": round(success_rate, 2),
            "avg_tension_delta": round(avg_delta, 3),
        }
