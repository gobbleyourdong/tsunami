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
        """Disabled for zero-shot (2026-04-13). The hard gates were misfiring
        repeatedly in smoke v6: model would file_write → shell_exec → undertow,
        then PHASE GATE would say 'not compiled' (build_passed not set even
        though build succeeded), forcing model into a build → undertow →
        message_result loop. The downstream _check_deliverable_complete in
        message.py still catches real shippable bugs (stub components, ReDoS,
        broken imgs, dead inputs, scaffold-unchanged). Re-enable behind a
        strict-gates flag if shippable-without-QA becomes a problem.
        Transitions still tracked in record() for telemetry."""
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

    def context_note(self, scaffold_kind: str = "react-app") -> str | None:
        """Phase-aware guidance note. Returns None if no nudge needed.

        Only fires when the agent is stalling in a phase. Early iterations
        get no nudges — let the model work.

        scaffold_kind (default 'react-app') adjusts the redirect message
        for gamedev tasks — calling project_init / file_write(App.tsx)
        on a gamedev task contradicts the GAMEDEV OVERRIDE and has
        caused live read-spirals (Round J 2026-04-20).
        """
        is_gamedev = scaffold_kind == "gamedev"
        if self.phase == Phase.SCAFFOLD and self.iters_in_phase >= 4:
            if is_gamedev:
                return (
                    "[PHASE:SCAFFOLD-gamedev] 4 iterations without "
                    "emitting a design. Call emit_design(design={...}, "
                    "project_name='...') NOW. Do NOT call project_init "
                    "— gamedev scaffold is engine-only. The wave reads "
                    "schema.ts + catalog.ts, composes entities + mechanics "
                    "+ scenes, then ships via emit_design."
                )
            return (
                "[PHASE:SCAFFOLD] 4 iterations without scaffolding. "
                "Call project_init to set up the project NOW."
            )

        if self.phase == Phase.WRITE:
            if self.iters_in_phase >= 5 and self.files_written == 0:
                if is_gamedev:
                    return (
                        "[PHASE:WRITE-gamedev] 5 iterations without "
                        "emit_design. The gamedev deliverable is "
                        "public/game_definition.json — call emit_design, "
                        "NOT file_write(App.tsx). Use entity names from "
                        "the CONTENT CATALOG directive in your user_message."
                    )
                return (
                    "[PHASE:WRITE] 5 iterations without writing any files. "
                    "STOP generating images now — you have enough assets. "
                    "Call file_write on src/App.tsx with the full page code. "
                    "Missing images will render as broken <img> — that is "
                    "FINE, the build still passes and the vision gate will "
                    "flag anything critical. Shipping compiled code matters "
                    "more than having every asset ready."
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
