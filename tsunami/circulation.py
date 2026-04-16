"""Circulation — circuit-breaker state machine for race-mode ad-hoc counters.

Oceanic circulation patterns flow, eddy (stall), probe (tentative resume),
or break (terminal). This module replaces the two race-mode getattr-counters
in agent.py with a single named abstraction:

- Site A: ``_total_400s`` context-overflow counter (agent.py:1056-1085)
- Site B: ``_stall_count`` read-spiral counter (agent.py:1278-1296)

Both sites count a predicate-matching event class and take a structured exit
at threshold. A ``Circulation`` instance owns: threshold, cool-down, recovery
semantics, and two callbacks (``on_eddy`` at threshold, ``on_trip`` at terminal).

States:

    flowing  --event (count < threshold)--> flowing
    flowing  --event (count == threshold)--> eddying   [on_eddy fires]
    eddying  --cooldown_iters elapsed---->  probing
    probing  --event---------------------->  broken    [on_trip fires; terminal]
    probing  --recovery_iters elapsed----->  flowing   [count reset]

The design doc (prior /loop pass) lives at ``/tmp/tech_debt_cat2_design.md``.
This module is NOT wired into agent.py yet — the live eval holds
``/tmp/eval_tiered.lock`` and imports ``tsunami.agent`` in-process, so edits
to the call sites are deferred to the eval-stop window.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger("tsunami.circulation")


# State names as module-level constants so callers avoid string typos.
FLOWING = "flowing"
EDDYING = "eddying"
PROBING = "probing"
BROKEN = "broken"

_VALID_STATES = (FLOWING, EDDYING, PROBING, BROKEN)


@dataclass
class Circulation:
    """Circuit-breaker with cool-down and probe-recovery.

    Parameters
    ----------
    name
        Identifier used in log lines (``context_overflow`` | ``read_spiral``).
    threshold
        Event count at which ``flowing`` transitions to ``eddying`` and
        ``on_eddy`` fires. Default 3 matches both current sites.
    cooldown_iters
        Iterations to wait in ``eddying`` before advancing to ``probing``.
        During cool-down, events are still counted but do not trip.
    recovery_iters
        Consecutive non-events in ``probing`` required to reset to ``flowing``.
    on_eddy
        Callback fired exactly once, on the ``flowing -> eddying`` transition.
        Use for "soft" corrective actions: compress context, inject warning.
    on_trip
        Callback fired exactly once, on the ``probing -> broken`` transition.
        Use for terminal exits: auto-deliver, set task_complete.

    Notes
    -----
    Both callbacks are called with no arguments. Callers close over any
    agent state they need via lambda capture (see design doc §4).

    ``tick(iter_n)`` must be called once per main-loop iteration to advance
    cool-down and recovery bookkeeping. ``event(iter_n)`` is called on each
    matching event and returns the post-transition state.
    """

    name: str
    threshold: int = 3
    cooldown_iters: int = 2
    recovery_iters: int = 5
    on_eddy: Optional[Callable[[], None]] = None
    on_trip: Optional[Callable[[], None]] = None

    # Runtime state (not user-facing config).
    state: str = FLOWING
    count: int = 0
    _eddy_at_iter: Optional[int] = field(default=None, repr=False)
    _clear_streak: int = field(default=0, repr=False)
    _tripped_once: bool = field(default=False, repr=False)

    def event(self, iter_n: int) -> str:
        """Record a matching event. Returns the post-transition state.

        State-specific behavior:

        - ``flowing``: increment count; if >= threshold, enter ``eddying``
          and fire ``on_eddy`` exactly once.
        - ``eddying``: increment count; stay in ``eddying`` (cool-down in
          progress). ``tick()`` is what advances out of this state.
        - ``probing``: any event here is decisive — go to ``broken`` and
          fire ``on_trip`` exactly once.
        - ``broken``: terminal, no-op. (Caller should have already exited
          the loop; this guards against late events.)
        """
        self.count += 1

        if self.state == FLOWING:
            if self.count >= self.threshold:
                self._transition_to_eddying(iter_n)
        elif self.state == EDDYING:
            # Cool-down in progress. Don't re-fire on_eddy; tick() advances.
            pass
        elif self.state == PROBING:
            # Half-open probe rejected — terminal.
            self._clear_streak = 0
            self._transition_to_broken()
        elif self.state == BROKEN:
            # Terminal; ignore. Logged at debug so it's auditable.
            log.debug(
                "circulation[%s] event after broken — ignored (count=%d)",
                self.name, self.count,
            )

        return self.state

    def tick(self, iter_n: int) -> None:
        """Advance cool-down / recovery bookkeeping. Call once per loop iter.

        - In ``eddying``: if ``cooldown_iters`` have elapsed since the
          eddy transition, advance to ``probing``.
        - In ``probing``: increment the clear-streak (a ``tick`` without a
          preceding ``event`` counts as a clear iteration). If the streak
          reaches ``recovery_iters``, reset to ``flowing`` with count=0.
        - Other states: no-op.

        Callers that want the clear-streak to track "iters since last event"
        accurately should call ``tick`` AFTER any possible ``event`` call
        in the same iteration. If an event fired this iter in ``probing``,
        the state is now ``broken`` and this tick is a no-op anyway.
        """
        if self.state == EDDYING:
            if self._eddy_at_iter is None:
                # Defensive: shouldn't happen, but recover by anchoring now.
                self._eddy_at_iter = iter_n
            elif iter_n - self._eddy_at_iter >= self.cooldown_iters:
                self.state = PROBING
                self._clear_streak = 0
                log.info(
                    "circulation[%s] eddying -> probing at iter=%d",
                    self.name, iter_n,
                )
        elif self.state == PROBING:
            self._clear_streak += 1
            if self._clear_streak >= self.recovery_iters:
                log.info(
                    "circulation[%s] probing -> flowing at iter=%d "
                    "(recovered after %d clear iters)",
                    self.name, iter_n, self._clear_streak,
                )
                self.state = FLOWING
                self.count = 0
                self._clear_streak = 0
                self._eddy_at_iter = None

    def reset(self) -> None:
        """Force reset to flowing. For tests and manual override only."""
        self.state = FLOWING
        self.count = 0
        self._eddy_at_iter = None
        self._clear_streak = 0
        self._tripped_once = False

    # --- internal transitions ------------------------------------------------

    def _transition_to_eddying(self, iter_n: int) -> None:
        self.state = EDDYING
        self._eddy_at_iter = iter_n
        log.warning(
            "circulation[%s] flowing -> eddying at iter=%d (count=%d, threshold=%d)",
            self.name, iter_n, self.count, self.threshold,
        )
        if self.on_eddy is not None:
            try:
                self.on_eddy()
            except Exception as exc:  # callbacks must not kill the agent loop
                log.exception(
                    "circulation[%s] on_eddy callback raised: %s", self.name, exc,
                )

    def _transition_to_broken(self) -> None:
        self.state = BROKEN
        if self._tripped_once:
            return
        self._tripped_once = True
        log.warning(
            "circulation[%s] probing -> broken (count=%d) — firing on_trip",
            self.name, self.count,
        )
        if self.on_trip is not None:
            try:
                self.on_trip()
            except Exception as exc:
                log.exception(
                    "circulation[%s] on_trip callback raised: %s", self.name, exc,
                )
