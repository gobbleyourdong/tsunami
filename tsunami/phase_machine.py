"""Phase state machine — enforced forward progress through the build pipeline.

Replaces ad-hoc stall detection with structural phase enforcement:

    SCAFFOLD → WRITE → BUILD → TEST → DELIVER

Each phase has hard-gated tools (blocked outside their phase) and transition
triggers (tool results that advance/retreat the phase). Backward transitions
only on explicit failure (build error → WRITE, QA fail → WRITE).

The 14 safety valves in agent.py become redundant once this is active.
They can coexist during validation, then be removed.

Convention beats instruction. Structure beats intention.
"""

from __future__ import annotations

import logging
from enum import IntEnum
from dataclasses import dataclass, field

log = logging.getLogger("tsunami.phase_machine")


class Phase(IntEnum):
    SCAFFOLD = 0
    WRITE = 1
    BUILD = 2
    TEST = 3
    DELIVER = 4


# Build success indicators from vite/webpack/etc output
BUILD_SUCCESS = ("built in", "build complete", "compiled successfully", "webpack compiled")


@dataclass
class PhaseMachine:
    """Enforced state machine for the agent build pipeline.

    Integration points in agent.py:
      1. __init__:        self.phase_machine = PhaseMachine()
      2. pre-scaffold:    self.phase_machine.skip_scaffold(path)
      3. before execute:  allowed, reason = self.phase_machine.gate(tool_name)
      4. after execute:   self.phase_machine.record(tool_name, args, result, is_error)
      5. system notes:    note = self.phase_machine.context_note()
    """

    phase: Phase = Phase.SCAFFOLD
    iters_in_phase: int = 0
    total_iters: int = 0
    files_written: int = 0
    build_passed: bool = False
    test_passed: bool = False
    project_path: str | None = None

    # Track what happened for richer context
    _last_build_error: str = ""
    _last_test_error: str = ""

    def gate(self, tool_name: str) -> tuple[bool, str]:
        """Hard gate: can this tool be called in the current phase?

        Returns (allowed, reason). Only blocks critical violations:
          - message_result before build passes
          - message_result before any files written

        Everything else is allowed — the model may legitimately skip phases.
        Transitions are tracked in record(), not enforced here.
        """
        if tool_name == "message_result":
            # Conversational responses (no project) always pass
            if not self.project_path and self.files_written == 0:
                return True, ""

            if self.files_written == 0:
                return False, (
                    "PHASE GATE: No code written yet. "
                    "Call file_write to create src/App.tsx first."
                )

            if not self.build_passed:
                return False, (
                    "PHASE GATE: Code written but not compiled. "
                    "Run the build first: shell_exec with command "
                    "'cd workspace/deliverables/{project} && npx vite build'."
                    .format(project=self.project_path.split("/")[-1] if self.project_path else "PROJECT")
                )

        # Block message_chat stalls during build tasks.
        # After writing code, the only forward move is building — not chatting.
        # This kills the IH03 failure mode: 7 writes → chat loop → timeout.
        if tool_name == "message_chat" and self.phase == Phase.WRITE and self.files_written > 0:
            return False, (
                "PHASE GATE: Code written but not compiled. "
                "Run the build: shell_exec with command "
                "'cd workspace/deliverables/{project} && npx vite build'. "
                "Do NOT chat — build first."
                .format(project=self.project_path.split("/")[-1] if self.project_path else "PROJECT")
            )

        return True, ""

    def record(self, tool_name: str, args: dict, result_content: str, is_error: bool):
        """Record a tool call. Detect and execute phase transitions.

        Call this AFTER tool execution with the result.
        """
        self.iters_in_phase += 1
        self.total_iters += 1
        old = self.phase

        # --- Track state ---

        if tool_name in ("file_write", "file_edit"):
            self.files_written += 1

        if tool_name == "project_init" and not is_error:
            name = args.get("name", "")
            if name:
                self.project_path = f"workspace/deliverables/{name}"

        # --- Forward transitions ---

        if tool_name == "project_init" and not is_error:
            self._advance(Phase.WRITE)

        elif tool_name in ("file_write", "file_edit") and self.phase < Phase.WRITE:
            # Model skipped scaffold, went straight to writing — accept it
            self._advance(Phase.WRITE)

        elif tool_name == "shell_exec" and not is_error:
            content_lower = result_content.lower() if result_content else ""
            if any(s in content_lower for s in BUILD_SUCCESS):
                self.build_passed = True
                self._last_build_error = ""
                self._advance(Phase.TEST)

        elif tool_name == "undertow" and not is_error:
            # Undertow pass = test passed
            if "passed" in (result_content or "").lower() or not is_error:
                self.test_passed = True
                self._last_test_error = ""
                self._advance(Phase.DELIVER)

        # --- Backward transitions ---

        if tool_name == "shell_exec" and is_error and self.phase >= Phase.BUILD:
            self._last_build_error = (result_content or "")[:200]
            self._retreat(Phase.WRITE, "build failed")

        if tool_name == "undertow" and is_error and self.phase >= Phase.TEST:
            self._last_test_error = (result_content or "")[:200]
            self._retreat(Phase.WRITE, "QA failed")

        if old != self.phase:
            log.info(f"Phase: {old.name} → {self.phase.name} (iter {self.total_iters})")

    def skip_scaffold(self, project_path: str | None = None):
        """Pre-existing project detected — jump to WRITE."""
        if project_path:
            self.project_path = project_path
        self._advance(Phase.WRITE)
        log.info(f"Phase: scaffold skipped → WRITE (project: {project_path})")

    def context_note(self) -> str | None:
        """Phase-aware guidance note. Returns None if no nudge needed.

        Only fires when the agent is stalling in a phase. Early iterations
        get no nudges — let the model work.
        """
        if self.phase == Phase.SCAFFOLD and self.iters_in_phase >= 4:
            return (
                "[PHASE:SCAFFOLD] 4 iterations without scaffolding. "
                "Call project_init to set up the project NOW."
            )

        if self.phase == Phase.WRITE:
            if self.iters_in_phase >= 8 and self.files_written == 0:
                return (
                    "[PHASE:WRITE] 8 iterations without writing any files. "
                    "Call file_write to create code NOW."
                )
            if self.files_written >= 1 and self.iters_in_phase >= 6:
                return (
                    "[PHASE:WRITE] Code written. Time to compile. "
                    "Run: shell_exec with 'npx vite build'."
                )

        if self.phase == Phase.BUILD and self.iters_in_phase >= 4:
            return (
                "[PHASE:BUILD] 4 build attempts without success. "
                "Read the error, fix the code with file_edit, then rebuild."
            )

        if self.phase == Phase.TEST and self.iters_in_phase >= 4:
            return (
                "[PHASE:TEST] Testing phase complete. "
                "Call message_result to deliver the finished app."
            )

        return None

    def status(self) -> dict:
        """Current state for logging/debugging."""
        return {
            "phase": self.phase.name,
            "iters_in_phase": self.iters_in_phase,
            "total_iters": self.total_iters,
            "files_written": self.files_written,
            "build_passed": self.build_passed,
            "test_passed": self.test_passed,
            "project_path": self.project_path,
        }

    def _advance(self, target: Phase):
        """Move forward. Only advances, never retreats."""
        if target > self.phase:
            self.phase = target
            self.iters_in_phase = 0

    def _retreat(self, target: Phase, reason: str):
        """Move backward on failure. Resets phase timer."""
        if target < self.phase:
            log.info(f"Phase retreat: {self.phase.name} → {target.name} ({reason})")
            self.phase = target
            self.iters_in_phase = 0
            # Don't clear build_passed — it may have passed earlier,
            # the current failure is a regression from an edit
