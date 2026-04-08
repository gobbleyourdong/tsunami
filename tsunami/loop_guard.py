"""Loop guard — detect and break agent stall patterns.

Three detection layers (from AgentPatterns.tech):
1. Hard loop: identical tool + args repeated 3x
2. Soft loop: same tool type repeated 5x (even with different args)
3. Semantic loop: no forward progress for N iterations

When a loop is detected, the guard returns a forced action that
overrides the model's next tool choice.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

log = logging.getLogger("tsunami.loop_guard")

HARD_LOOP_THRESHOLD = 3    # identical (tool, args_hash) repeated
SOFT_LOOP_THRESHOLD = 5    # same tool_name repeated
PROGRESS_WINDOW = 8        # iterations without progress


@dataclass
class LoopDetection:
    """Result of loop analysis."""
    detected: bool = False
    loop_type: str = ""  # "hard", "soft", "progress"
    description: str = ""
    forced_action: str = ""  # tool name to force, or "" for nudge only


def _fingerprint(tool_name: str, args: dict) -> str:
    """Hash a tool call for dedup detection."""
    args_str = str(sorted(args.items()))[:200]
    return hashlib.md5(f"{tool_name}:{args_str}".encode()).hexdigest()[:12]


class LoopGuard:
    """Track tool calls and detect stall patterns."""

    def __init__(self):
        self.fingerprints: list[str] = []
        self.tool_names: list[str] = []
        self.progress_marks: list[bool] = []  # True = made progress

    def record(self, tool_name: str, args: dict, made_progress: bool):
        """Record a tool call."""
        fp = _fingerprint(tool_name, args)
        self.fingerprints.append(fp)
        self.tool_names.append(tool_name)
        self.progress_marks.append(made_progress)

    def check(self) -> LoopDetection:
        """Check for loop patterns. Returns detection result."""

        # Hard loop: 3 identical fingerprints in a row
        if len(self.fingerprints) >= HARD_LOOP_THRESHOLD:
            recent = self.fingerprints[-HARD_LOOP_THRESHOLD:]
            if len(set(recent)) == 1:
                tool = self.tool_names[-1]
                return LoopDetection(
                    detected=True,
                    loop_type="hard",
                    description=f"Identical {tool} call repeated {HARD_LOOP_THRESHOLD}x",
                    forced_action=self._suggest_break_action(tool),
                )

        # Soft loop: same tool type 5x in a row
        if len(self.tool_names) >= SOFT_LOOP_THRESHOLD:
            recent = self.tool_names[-SOFT_LOOP_THRESHOLD:]
            if len(set(recent)) == 1:
                tool = recent[0]
                return LoopDetection(
                    detected=True,
                    loop_type="soft",
                    description=f"{tool} called {SOFT_LOOP_THRESHOLD}x consecutively",
                    forced_action=self._suggest_break_action(tool),
                )

        # Progress stall: no progress for N iterations
        if len(self.progress_marks) >= PROGRESS_WINDOW:
            recent = self.progress_marks[-PROGRESS_WINDOW:]
            if not any(recent):
                return LoopDetection(
                    detected=True,
                    loop_type="progress",
                    description=f"No progress in {PROGRESS_WINDOW} iterations",
                    forced_action="project_init",
                )

        return LoopDetection(detected=False)

    def _suggest_break_action(self, stuck_tool: str) -> str:
        """Suggest which tool to force based on what we're stuck on."""
        read_tools = {"file_read", "match_grep", "match_glob", "file_list"}
        search_tools = {"search_web", "browser_navigate"}

        if stuck_tool in read_tools or stuck_tool in search_tools:
            # Stuck reading/searching → force building
            return "project_init"
        elif stuck_tool == "shell_exec":
            # Stuck running commands → force writing code
            return "file_write"
        elif stuck_tool == "file_write":
            # Stuck writing the same file → force build check
            return "shell_exec"
        else:
            return "project_init"

    def reset(self):
        """Reset after a successful delivery."""
        self.fingerprints.clear()
        self.tool_names.clear()
        self.progress_marks.clear()
