"""Progress-signal detection — condition-based stall/cap heuristics.

Layer 3 of the 'eliminate hardcoded brittle surfaces' pass. Iter-count
triggers were sprinkled across agent.py — `iteration == 10`,
`iteration > 30`, `iteration > 60`, `iteration % 5 == 0`, etc — with
each call site duplicating its own "no writes recently" computation.

Each trigger mixes THREE concerns inline:
  1. "has enough time elapsed?" (iter count)
  2. "what's the progress signal?" (tool_history analysis)
  3. "what do we do?" (nudge / exit / system_note)

This module isolates (2) into named condition functions and (1)+(3)
into ProgressSignal records, so the agent's main loop calls:

    signals = detect_progress_signals(iter_n, tool_history, flags)
    for sig in signals:
        if sig.action == "nudge":  ...
        if sig.action == "exit":   ...

Adding a new signal = one function + one entry in the dispatcher.
Removing one = delete the entry, not surgery across 500 lines.

Today's signals (migrated from inline):
  no_code_writes       — iter_floor + writes_in_window == 0
  long_stall           — iter_floor + writes in last N == 0 → force exit
  hard_cap             — iter_floor alone → force exit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

log = logging.getLogger("tsunami.progress")


# Tool names that count as "real code-write progress" — image gen and
# reads don't count, because long image-gen phases can easily consume
# 10+ iters without being a stall.
_CODE_WRITE_TOOLS: frozenset[str] = frozenset({
    "file_write", "file_edit", "file_append", "project_init",
})


@dataclass
class ProgressSignal:
    """A single progress observation that the agent should react to."""
    name: str
    action: str                  # "nudge" | "exit" | "advisory"
    message: str = ""            # text for add_system_note / log
    log_level: str = "warning"   # "info" | "warning" | "error"
    exit_reason: str = ""        # populated when action=="exit"


# ── Condition helpers ──────────────────────────────────────────────


def _count_in_window(
    history: list[str],
    tools: Iterable[str],
    window: int | None = None,
) -> int:
    """Count occurrences of any `tools` in the last `window` entries of
    `history`. `window=None` means the whole history.
    """
    recent = history[-window:] if window is not None else history
    target = set(tools)
    return sum(1 for t in recent if t in target)


def no_code_writes_in(history: list[str], window: int | None = None) -> bool:
    """True if zero code-write tools appear in the recent window."""
    return _count_in_window(history, _CODE_WRITE_TOOLS, window) == 0


# ── Signal detectors ───────────────────────────────────────────────


def detect_progress_signals(
    iteration: int,
    tool_history: list[str],
    *,
    early_nudge_at: int = 10,
    stall_check_after: int = 30,
    stall_window: int = 20,
    hard_cap: int = 60,
) -> list[ProgressSignal]:
    """Return the list of progress signals that fire this iteration.

    Defaults match the pre-refactor agent.py values. Each threshold is
    a parameter so callers can tune per-scaffold / per-task (gamedev
    runs need longer nudges; utility-app runs can cap sooner).
    """
    out: list[ProgressSignal] = []

    # Early nudge: drone has elapsed iter budget but written nothing yet.
    if (iteration == early_nudge_at
            and no_code_writes_in(tool_history)):
        out.append(ProgressSignal(
            name="no_code_writes",
            action="nudge",
            message=(
                f"Pressure building. {iteration} iterations, zero writes. "
                "Write App.tsx NOW."
            ),
        ))

    # Long stall: past the stall-floor AND zero writes in recent window.
    if (iteration > stall_check_after
            and no_code_writes_in(tool_history, window=stall_window)):
        out.append(ProgressSignal(
            name="long_stall",
            action="exit",
            message=(
                f"Safety valve: {iteration} iters, 0 writes in last "
                f"{stall_window} — forcing exit"
            ),
            exit_reason="Task ended — no progress detected.",
        ))

    # Hard cap: iter count alone. Catches runaway generation loops.
    if iteration > hard_cap:
        out.append(ProgressSignal(
            name="hard_cap",
            action="exit",
            message=f"Hard cap: {iteration} iterations — forcing exit",
            exit_reason=f"Task ended after {iteration} iterations.",
        ))

    return out


__all__ = [
    "ProgressSignal",
    "detect_progress_signals",
    "no_code_writes_in",
]
