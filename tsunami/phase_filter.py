"""Phase-based tool filtering + model capability probing.

Extends the dynamic tool filter (chunk 4) with:
1. Per-phase tool subsets — only show relevant tools for current phase
2. Auto-detection of phase transitions from tool usage patterns
3. Model capability probing — classify model as basic/intermediate/advanced

Phases:
  RESEARCH: gathering info (search_web, file_read, match_grep, match_glob)
  PLAN:     structuring approach (plan_update, message_info)
  BUILD:    writing code (file_write, file_edit, shell_exec, project_init, generate_image)
  VERIFY:   testing (shell_exec for build/test only, file_read)
  DELIVER:  presenting result (message_result)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("tsunami.phase_filter")

# Phase definitions with allowed tools
PHASE_TOOLS: dict[str, set[str]] = {
    "RESEARCH": {"search_web", "file_read", "file_list", "match_grep", "match_glob", "browser_navigate"},
    "PLAN": {"plan_update", "message_info", "message_ask"},
    "BUILD": {"file_write", "file_edit", "shell_exec", "project_init", "generate_image", "plan_update"},
    "VERIFY": {"shell_exec", "file_read", "match_grep"},
    "DELIVER": {"message_result", "message_info"},
}

# Tools that are always available regardless of phase
UNIVERSAL_TOOLS = {"message_ask", "message_info", "plan_update"}

# Capability levels
CAPABILITY_LEVELS = ("basic", "intermediate", "advanced")


def detect_phase(tool_history: list[str], window: int = 10) -> str:
    """Detect current phase from recent tool usage patterns.

    Uses a sliding window over the last N tool calls to classify
    what phase the agent is in.
    """
    if len(tool_history) < 3:
        return "RESEARCH"  # start by gathering info

    recent = tool_history[-window:]
    total = len(recent)

    # Count tool categories
    research = sum(1 for t in recent if t in PHASE_TOOLS["RESEARCH"])
    build = sum(1 for t in recent if t in PHASE_TOOLS["BUILD"])
    verify = sum(1 for t in recent if t in ("shell_exec",) and t not in PHASE_TOOLS["BUILD"])

    # Delivery detection — most recent tool
    if recent[-1] == "message_result":
        return "DELIVER"

    # Phase classification by majority
    if research / total > 0.6:
        return "RESEARCH"

    # Build = writes + edits
    writes = sum(1 for t in recent if t in ("file_write", "file_edit", "project_init"))
    if writes / total > 0.4:
        return "BUILD"

    # Verify = mostly shell_exec after some writes
    shells = sum(1 for t in recent if t == "shell_exec")
    if shells / total > 0.4 and any(t in ("file_write", "file_edit") for t in tool_history[-20:]):
        return "VERIFY"

    # Plan = message/plan heavy
    plans = sum(1 for t in recent if t in ("plan_update", "message_info"))
    if plans / total > 0.3:
        return "PLAN"

    return "BUILD"  # default to building


def get_phase_tools(phase: str) -> set[str]:
    """Get the set of tools available for a phase.

    Always includes universal tools.
    """
    tools = PHASE_TOOLS.get(phase, set())
    return tools | UNIVERSAL_TOOLS


def filter_tools_for_phase(
    all_tools: list[str],
    tool_history: list[str],
) -> tuple[str, list[str]]:
    """Filter available tools based on detected phase.

    Returns (detected_phase, filtered_tool_names).
    """
    phase = detect_phase(tool_history)
    allowed = get_phase_tools(phase)

    # In BUILD phase, allow everything (don't restrict building)
    if phase == "BUILD":
        return phase, all_tools

    # For other phases, filter but keep at least the universal tools
    filtered = [t for t in all_tools if t in allowed]

    # Safety: if filtering removes too many tools, don't filter
    if len(filtered) < 3:
        return phase, all_tools

    return phase, filtered


def generate_phase_note(phase: str, tool_history: list[str]) -> str | None:
    """Generate a phase-transition note for the agent.

    Returns None if no transition guidance is needed.
    """
    if len(tool_history) < 2:
        return None

    recent = tool_history[-10:]

    # Detect transitions
    if phase == "RESEARCH" and len(tool_history) > 15:
        research_count = sum(1 for t in recent if t in PHASE_TOOLS["RESEARCH"])
        if research_count >= 7:
            return "[PHASE] You've been researching for a while. Consider transitioning to BUILD."

    if phase == "BUILD":
        writes = sum(1 for t in recent if t in ("file_write", "file_edit"))
        if writes >= 2 and "shell_exec" not in recent[-3:]:
            return "[PHASE] You've written several files. Run a build check (shell_exec) to verify."

    if phase == "VERIFY":
        shells = sum(1 for t in recent if t == "shell_exec")
        errors = sum(1 for t in recent if t == "shell_exec")  # proxy
        if shells >= 3:
            return "[PHASE] Verification complete. Consider delivering the result."

    return None


class ModelCapability:
    """Probe and persist model capability level.

    On first run, sends a simple coding task to the model and measures
    quality. Result persisted to config so we don't re-probe every session.
    """

    CONFIG_KEY = "model_capability"

    def __init__(self, config_path: str | Path = ""):
        self.config_path = Path(config_path) if config_path else None
        self.level: str = "intermediate"  # default

    def load(self) -> str:
        """Load persisted capability level."""
        if self.config_path and self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text())
                level = data.get(self.CONFIG_KEY, "intermediate")
                if level in CAPABILITY_LEVELS:
                    self.level = level
            except (json.JSONDecodeError, KeyError):
                pass
        return self.level

    def save(self):
        """Persist capability level."""
        if not self.config_path:
            return
        data = {}
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text())
            except json.JSONDecodeError:
                pass
        data[self.CONFIG_KEY] = self.level
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(data, indent=2))

    def classify(self, response: str) -> str:
        """Classify model capability from a probe response.

        The probe asks: "Write a TypeScript function that reverses a string."

        basic: no function, wrong syntax, or nonsensical
        intermediate: correct function but no types or edge cases
        advanced: typed, handles edge cases, clean code
        """
        response_lower = response.lower()

        # Check for function presence
        has_function = "function" in response_lower or "=>" in response
        has_typescript = "string" in response_lower and (":" in response)
        has_reverse = "reverse" in response_lower or "split" in response_lower
        has_edge_case = "null" in response_lower or "undefined" in response_lower or "length" in response_lower

        if not has_function or not has_reverse:
            self.level = "basic"
        elif has_typescript and has_edge_case:
            self.level = "advanced"
        elif has_function and has_reverse:
            self.level = "intermediate"
        else:
            self.level = "basic"

        return self.level

    @property
    def is_capable(self) -> bool:
        """Can the model handle complex multi-step tasks?"""
        return self.level in ("intermediate", "advanced")
