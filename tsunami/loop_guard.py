"""Loop guard — detect agent stall patterns.

Three detection layers (from AgentPatterns.tech):
1. Hard loop: identical tool + args repeated 3x
2. Soft loop: same tool type repeated 5x (even with different args)
3. Semantic loop: no forward progress for N iterations

When a loop is detected, the guard returns a `suggested_action` (a tool
name) that the caller injects into the state as a system note — the model
is strongly steered toward it but NOT forced. A real hard override would
require intercepting the next _step before the model runs; the current
nudge-only approach leaves the model in control and is sufficient for
the cases observed in practice (QA-2 iter 11/12 build-loop was addressed
at the feedback-tracker layer instead — see tsunami/feedback.py).
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
    forced_action: str = ""  # tool name suggested to the agent via system note;
                             # "" if no specific alternative is suggested. Named
                             # `forced_action` for historical reasons — the
                             # current consumer nudges via state.add_system_note,
                             # it does NOT intercept the model's next choice.


def _fingerprint(tool_name: str, args: dict) -> str:
    """Hash a tool call for dedup detection. Hashes the FULL args — truncating
    misfires on file_write/file_edit where successive rewrites share the first
    200 chars (path + `import React...`) but have substantially different
    bodies. Pomodoro eval pre-fix: three ~180-line App.tsx rewrites with
    different internal logic all hashed identical, tripping the 3x hard-loop
    and killing the run at 600s. md5 on 6 KB of args is trivially cheap."""
    args_str = str(sorted(args.items()))
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
            recent_tools = self.tool_names[-SOFT_LOOP_THRESHOLD:]
            if len(set(recent_tools)) == 1:
                tool = recent_tools[0]
                # Suppress for generate_image when each call targets a
                # DISTINCT fingerprint (different prompt or save_path) —
                # briefs that ask for 9+ images need 9+ consecutive
                # generate_image calls and that's legitimate progress,
                # not a loop. Only fire when the drone is churning on
                # the same-or-near-same generation repeatedly.
                if tool == "generate_image":
                    recent_fps = self.fingerprints[-SOFT_LOOP_THRESHOLD:]
                    if len(set(recent_fps)) >= SOFT_LOOP_THRESHOLD - 1:
                        # 4+ distinct fingerprints out of 5 calls — real
                        # multi-image work, not a stall.
                        pass
                    else:
                        return LoopDetection(
                            detected=True,
                            loop_type="soft",
                            description=f"{tool} called {SOFT_LOOP_THRESHOLD}x consecutively with repeated targets",
                            forced_action=self._suggest_break_action(tool),
                        )
                else:
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
        """Suggest which tool to force based on what we're stuck on.

        Project-aware: if project_init already happened (detected by looking at
        earlier fingerprints), suggesting project_init again is useless —
        model will either refuse or blow away work. In that case suggest
        file_edit for read-loops and message_result for write-loops (which
        usually indicates "task done, just ship it").
        """
        read_tools = {"file_read", "match_grep", "match_glob", "file_list"}
        search_tools = {"search_web", "browser_navigate"}

        # Detect whether project_init already ran — scan tool_names history.
        project_already_init = "project_init" in self.tool_names

        if stuck_tool in read_tools:
            # Stuck re-reading files (common after tsc failures) — the model
            # is looking for answers in source it's already seen. Force it
            # to use file_edit to ACT on the error instead of looking more.
            if project_already_init:
                return "file_edit"
            return "project_init"
        elif stuck_tool in search_tools:
            return "project_init"
        elif stuck_tool == "shell_exec":
            # Stuck running commands → force writing code
            return "file_write"
        elif stuck_tool == "file_write":
            # Stuck writing the same file → force build check, OR if the
            # model has already run builds, just ship what it has.
            if "shell_exec" in self.tool_names:
                return "message_result"
            return "shell_exec"
        elif stuck_tool == "generate_image":
            # Stuck re-generating the same (or similar) images — drone is
            # burning inference on the image server instead of writing the
            # app that uses them. Force a file_write to pivot to App.tsx.
            # AURUM v13 burned 12 iters cycling through gt/r/x/one
            # regenerations with progressively vaguer prompts.
            return "file_write"
        else:
            return "project_init" if not project_already_init else "file_edit"

    def reset(self):
        """Reset after a successful delivery."""
        self.fingerprints.clear()
        self.tool_names.clear()
        self.progress_marks.clear()
