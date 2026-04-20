"""Phase-based tool filtering.

Per-phase tool subsets + auto-detection of phase transitions from
tool usage patterns.

Phases:
  RESEARCH: gathering info (search_web, file_read)
  PLAN:     structuring approach (message_chat for clarification)
  BUILD:    writing code (file_write, file_edit, shell_exec, project_init, generate_image, riptide)
  VERIFY:   testing (shell_exec for build/test, undertow for QA, file_read)
  DELIVER:  presenting result (message_result)

Updated after the 11-tool cleanup: dropped match_grep, match_glob,
plan_update, message_info, message_ask, browser_navigate from phase sets.
"""

from __future__ import annotations

import logging

log = logging.getLogger("tsunami.phase_filter")

# Phase definitions with allowed tools — must be subset of the 11 live tools
PHASE_TOOLS: dict[str, set[str]] = {
    "RESEARCH": {"search_web", "file_read"},
    "PLAN": {"message_chat"},
    "BUILD": {"file_write", "file_edit", "shell_exec", "project_init", "generate_image", "riptide"},
    "VERIFY": {"shell_exec", "file_read", "undertow"},
    "DELIVER": {"message_result"},
}

# Tools that are always available regardless of phase
UNIVERSAL_TOOLS = {"message_chat"}

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

    # Plan = conversational-heavy (message_chat clarifying before building)
    plans = sum(1 for t in recent if t == "message_chat")
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
        if shells >= 3:
            return "[PHASE] Verification complete. Consider delivering the result."

    return None


# NB: ModelCapability (TypeScript-reverse-string probe + grep classifier)
# was removed 2026-04-13 — only used by tests, never wired into the agent.
# If we ever want capability gating, do it from real eval scores, not a
# one-off probe.
