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
# Gamedev-specific threshold — Round U 2026-04-20 timed out with 6
# file_reads when iter 5's emit_design generation ran slow. Tripping
# at 4 file_reads saves one iteration's worth of budget (~5-10 min of
# unused token budget when first-token is slow). React scaffolds keep
# the old threshold because a 5-read design phase for a visual app
# is sometimes legitimate.
SOFT_LOOP_THRESHOLD_GAMEDEV = 4
# Scaffold-first gamedev: file_read is NEVER legitimate in the
# drone's job (data/*.json, schema.ts, catalog.ts, App.test.tsx all
# inlined in the system prompt — see tsunami/prompt.py:264-269,319-
# 328). Round 1's _scaffold_first_block already returns is_error on
# data/*.json reads, but the drone can still spiral on src/*.ts /
# node_modules/... / plans/current.md. Session 1776736395 captured a
# spiral where the generic HARD_LOOP_THRESHOLD=3 let the drone burn
# 3 iterations of the same file_read before firing. For scaffold-
# first, two identical file_read calls is already a strong enough
# signal to intervene — the drone has already been told once.
HARD_LOOP_THRESHOLD_SCAFFOLD_FIRST_READ = 2
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
        # Per-save-path generate_image counter. When a drone re-generates
        # the same save_path 3+ times with varied prompts (indecision
        # about palette/composition), treat as a hard loop even though
        # the full-args fingerprint differs. AURUM v22/v24 stuck on
        # models/{gt,r,x,one}.png for 10+ iters cycling color-schemes.
        self.gen_counts: dict[str, int] = {}
        # Recent generate_image prompts (lowercased, stripped) for
        # prompt-literalism detection: drone pastes the same brand-brief
        # template body verbatim for different models instead of filling
        # in the <subject> placeholder with per-asset descriptors.
        self._recent_gen_prompts: list[str] = []
        # Set by agent.py at pre-scaffold / _swap_in_edit_prompt time.
        # Declared here so check() / check_no_progress() can read them
        # as direct attributes instead of `getattr(..., default)` across
        # 9 sites. Defaults mirror the pre-declared fallbacks verbatim.
        self._scaffold_kind: str = ""
        self._gamedev_mode: str = "legacy"

    def record(self, tool_name: str, args: dict, made_progress: bool):
        """Record a tool call."""
        fp = _fingerprint(tool_name, args)
        self.fingerprints.append(fp)
        self.tool_names.append(tool_name)
        self.progress_marks.append(made_progress)
        if tool_name == "generate_image":
            save_path = str(args.get("save_path", "")).strip()
            if save_path:
                self.gen_counts[save_path] = self.gen_counts.get(save_path, 0) + 1
            # Normalize for literal-identity compare — strip whitespace
            # and lowercase so "Sleek..." / "sleek...  " both land as
            # the same prompt.
            prompt = str(args.get("prompt", "")).strip().lower()
            self._recent_gen_prompts.append(prompt)
            # Bound history so old iters don't linger
            if len(self._recent_gen_prompts) > 16:
                self._recent_gen_prompts = self._recent_gen_prompts[-16:]
        else:
            self._recent_gen_prompts.append("")

    def check(self, scaffold_kind: str = "react-app") -> LoopDetection:
        """Check for loop patterns. Returns detection result.

        scaffold_kind influences the forced_action suggestion —
        gamedev tasks should be routed to emit_design rather than
        project_init when a read-spiral triggers. Round K 2026-04-20
        captured 'LOOP DETECTED: ... call project_init' firing on a
        gamedev run directly after the GAMEDEV OVERRIDE said not to.
        """
        self._scaffold_kind = scaffold_kind

        # Tighter hard loop for scaffold-first gamedev file_read:
        # 2 identical file_read calls fires. See HARD_LOOP_THRESHOLD_
        # SCAFFOLD_FIRST_READ rationale above. Only applies to file_read
        # — scaffold-first drones edit data/*.json via file_write at
        # legitimate repeat counts, so those stay on the generic
        # threshold.
        is_scaffold_first_gd = (
            self._scaffold_kind == "gamedev"
            and self._gamedev_mode == "scaffold_first"
        )
        if (is_scaffold_first_gd
                and len(self.fingerprints) >= HARD_LOOP_THRESHOLD_SCAFFOLD_FIRST_READ
                and self.tool_names[-1] == "file_read"):
            recent = self.fingerprints[-HARD_LOOP_THRESHOLD_SCAFFOLD_FIRST_READ:]
            recent_tools = self.tool_names[-HARD_LOOP_THRESHOLD_SCAFFOLD_FIRST_READ:]
            if (len(set(recent)) == 1
                    and all(t == "file_read" for t in recent_tools)):
                return LoopDetection(
                    detected=True,
                    loop_type="hard",
                    description=(
                        f"Identical file_read call repeated "
                        f"{HARD_LOOP_THRESHOLD_SCAFFOLD_FIRST_READ}x in "
                        f"scaffold-first gamedev. Data files are inlined — "
                        f"use file_write to edit, then message_result."
                    ),
                    forced_action=self._suggest_break_action("file_read"),
                )

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

        # Per-save-path generate_image churn: drone re-generating the
        # same asset 3+ times (prompt variations, indecision). Hard-loop
        # intercept — fingerprints differ so the classic hard-loop
        # check above misses this. Forces file_write to pivot to code.
        if self.tool_names and self.tool_names[-1] == "generate_image":
            for path, count in self.gen_counts.items():
                if count >= 3:
                    return LoopDetection(
                        detected=True,
                        loop_type="hard",
                        description=f"generate_image({path!r}) re-run {count}x — drone stuck on one asset",
                        forced_action="file_write",
                    )

        # Prompt-literalism: drone uses the SAME generate_image prompt
        # across distinct save_paths (brand-brief template literal-
        # substitution failure). E.g. "sleek electric hypercar photographed
        # coast cliff..." passed 7x for gt/r/x/one + re-gens. Save_paths
        # differ so fingerprints differ and the classic checks above miss.
        # Track last-K prompts; fire if 4+ of the last 5 are literal
        # string-identical. Drone should substitute <subject> with
        # model-specific descriptors ("grand touring hypercar GT with
        # long hood...") not reuse the template verbatim.
        if (len(self.fingerprints) >= SOFT_LOOP_THRESHOLD
                and all(t == "generate_image"
                        for t in self.tool_names[-SOFT_LOOP_THRESHOLD:])):
            last_prompts = [p for p in self._recent_gen_prompts[-SOFT_LOOP_THRESHOLD:]
                            if p]
            if last_prompts and last_prompts.count(last_prompts[-1]) >= SOFT_LOOP_THRESHOLD - 1:
                return LoopDetection(
                    detected=True,
                    loop_type="hard",
                    description=(
                        f"generate_image prompt identical {SOFT_LOOP_THRESHOLD - 1}+ "
                        f"times across different save_paths — drone is pasting "
                        f"the brand-brief template without substituting per-asset "
                        f"descriptors"
                    ),
                    forced_action="file_write",
                )

        # Soft loop: same tool type N in a row. Gamedev uses a lower
        # threshold (4) to save iteration budget when first-token is slow.
        is_gamedev = self._scaffold_kind == "gamedev"
        soft_thresh = SOFT_LOOP_THRESHOLD_GAMEDEV if is_gamedev else SOFT_LOOP_THRESHOLD
        if len(self.tool_names) >= soft_thresh:
            recent_tools = self.tool_names[-soft_thresh:]
            if len(set(recent_tools)) == 1:
                tool = recent_tools[0]
                # Suppress for generate_image when each call targets a
                # DISTINCT fingerprint (different prompt or save_path) —
                # briefs that ask for 9+ images need 9+ consecutive
                # generate_image calls and that's legitimate progress,
                # not a loop. Only fire when the drone is churning on
                # the same-or-near-same generation repeatedly.
                if tool == "generate_image":
                    recent_fps = self.fingerprints[-soft_thresh:]
                    if len(set(recent_fps)) >= soft_thresh - 1:
                        # Most distinct fingerprints — real multi-image work, not a stall.
                        pass
                    else:
                        return LoopDetection(
                            detected=True,
                            loop_type="soft",
                            description=f"{tool} called {soft_thresh}x consecutively with repeated targets",
                            forced_action=self._suggest_break_action(tool),
                        )
                else:
                    return LoopDetection(
                        detected=True,
                        loop_type="soft",
                        description=f"{tool} called {soft_thresh}x consecutively",
                        forced_action=self._suggest_break_action(tool),
                    )

        # Progress stall: no progress for N iterations
        if len(self.progress_marks) >= PROGRESS_WINDOW:
            recent = self.progress_marks[-PROGRESS_WINDOW:]
            if not any(recent):
                # For gamedev, emit_design is the analog of project_init
                # for legacy engine-only; for scaffold-first, force
                # file_write (drone should be editing data/*.json).
                is_gamedev = self._scaffold_kind == "gamedev"
                mode = self._gamedev_mode
                if is_gamedev and mode == "scaffold_first":
                    stall_action = "file_write"
                elif is_gamedev:
                    stall_action = "emit_design"
                else:
                    stall_action = "project_init"
                return LoopDetection(
                    detected=True,
                    loop_type="progress",
                    description=f"No progress in {PROGRESS_WINDOW} iterations",
                    forced_action=stall_action,
                )

        return LoopDetection(detected=False)

    def _suggest_break_action(self, stuck_tool: str) -> str:
        """Suggest which tool to force based on what we're stuck on.

        Project-aware: if project_init already happened (detected by looking at
        earlier fingerprints), suggesting project_init again is useless —
        model will either refuse or blow away work. In that case suggest
        file_edit for read-loops and message_result for write-loops (which
        usually indicates "task done, just ship it").

        Scaffold-aware (Round K 2026-04-20 fix): for gamedev tasks,
        project_init is the WRONG tool (gamedev is engine-only) —
        suggest emit_design instead. emit_design + project_init are
        mutually exclusive by scaffold.
        """
        read_tools = {"file_read", "match_grep", "match_glob", "file_list"}
        search_tools = {"search_web", "browser_navigate"}
        is_gamedev = self._scaffold_kind == "gamedev"

        # Detect whether project_init already ran — scan tool_names history.
        project_already_init = "project_init" in self.tool_names
        # Detect whether emit_design already ran successfully (for gamedev)
        emit_design_already = "emit_design" in self.tool_names

        if stuck_tool in read_tools:
            # Stuck re-reading files — model is looking for answers in
            # source it's already seen. Force it to ACT.
            if is_gamedev:
                # Scaffold-first projects have a pre-provisioned data/
                # dir; the fix is to file_write a data/*.json, NOT to
                # call emit_design (which would overwrite the scaffold).
                # Detection: scaffold-first sets `_gamedev_mode` =
                # 'scaffold_first' on the loop-guard instance.
                mode = self._gamedev_mode
                if mode == "scaffold_first":
                    return "file_write"
                # Legacy engine-only flow: emit_design is the bootstrap.
                return "message_result" if emit_design_already else "emit_design"
            if project_already_init:
                return "file_edit"
            return "project_init"
        elif stuck_tool in search_tools:
            if is_gamedev:
                mode = self._gamedev_mode
                if mode == "scaffold_first":
                    return "file_write"
                return "emit_design" if not emit_design_already else "message_result"
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
            # For gamedev, the pivot is emit_design not file_write.
            if is_gamedev:
                return "emit_design" if not emit_design_already else "message_result"
            return "file_write"
        else:
            if is_gamedev:
                mode = self._gamedev_mode
                if mode == "scaffold_first":
                    return "file_write"
                return "emit_design" if not emit_design_already else "message_result"
            return "project_init" if not project_already_init else "file_edit"

    def reset(self):
        """Reset after a successful delivery."""
        self.fingerprints.clear()
        self.tool_names.clear()
        self.progress_marks.clear()
