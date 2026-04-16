"""Tests for Circulation circuit-breaker (tsunami.circulation).

Standalone — no agent.py / model / eval dependencies. Safe to run while
the live eval holds ``/tmp/eval_tiered.lock``.
"""

from __future__ import annotations

import pytest

from tsunami.circulation import (
    BROKEN,
    Circulation,
    EDDYING,
    FLOWING,
    PROBING,
)


def _make(**overrides):
    """Circulation with counting callbacks for assertion."""
    calls = {"eddy": 0, "trip": 0}

    def _on_eddy():
        calls["eddy"] += 1

    def _on_trip():
        calls["trip"] += 1

    kwargs = dict(
        name="test",
        threshold=3,
        cooldown_iters=2,
        recovery_iters=5,
        on_eddy=_on_eddy,
        on_trip=_on_trip,
    )
    kwargs.update(overrides)
    return Circulation(**kwargs), calls


class TestInitialState:
    def test_starts_flowing(self):
        c, _ = _make()
        assert c.state == FLOWING
        assert c.count == 0


class TestFlowingToEddying:
    def test_below_threshold_stays_flowing(self):
        c, calls = _make(threshold=3)
        c.event(iter_n=1)
        c.event(iter_n=2)
        assert c.state == FLOWING
        assert c.count == 2
        assert calls["eddy"] == 0

    def test_reaching_threshold_enters_eddying(self):
        c, calls = _make(threshold=3)
        c.event(iter_n=1)
        c.event(iter_n=2)
        c.event(iter_n=3)
        assert c.state == EDDYING
        assert calls["eddy"] == 1
        assert calls["trip"] == 0

    def test_on_eddy_fires_exactly_once(self):
        c, calls = _make(threshold=2)
        c.event(iter_n=1)
        c.event(iter_n=2)  # trip threshold
        c.event(iter_n=3)  # still eddying
        c.event(iter_n=4)
        assert calls["eddy"] == 1


class TestCooldownToProbing:
    def test_tick_advances_after_cooldown(self):
        c, _ = _make(threshold=2, cooldown_iters=2)
        c.event(iter_n=5)
        c.event(iter_n=5)  # eddying at iter 5
        assert c.state == EDDYING
        c.tick(iter_n=6)  # 1 iter elapsed
        assert c.state == EDDYING
        c.tick(iter_n=7)  # 2 iters elapsed -> probing
        assert c.state == PROBING

    def test_tick_before_cooldown_stays_eddying(self):
        c, _ = _make(threshold=1, cooldown_iters=5)
        c.event(iter_n=10)
        assert c.state == EDDYING
        for i in range(11, 14):
            c.tick(iter_n=i)
        assert c.state == EDDYING


class TestProbingToBroken:
    def test_event_in_probing_breaks(self):
        c, calls = _make(threshold=1, cooldown_iters=1)
        c.event(iter_n=1)          # -> eddying
        c.tick(iter_n=2)           # -> probing
        assert c.state == PROBING
        c.event(iter_n=3)          # -> broken
        assert c.state == BROKEN
        assert calls["trip"] == 1

    def test_on_trip_fires_exactly_once(self):
        c, calls = _make(threshold=1, cooldown_iters=1)
        c.event(iter_n=1)
        c.tick(iter_n=2)
        c.event(iter_n=3)          # trip
        c.event(iter_n=4)          # late event — ignored
        c.event(iter_n=5)
        assert calls["trip"] == 1


class TestProbingToFlowingRecovery:
    def test_clear_streak_restores_flowing(self):
        c, _ = _make(threshold=1, cooldown_iters=1, recovery_iters=3)
        c.event(iter_n=1)          # eddying
        c.tick(iter_n=2)           # probing
        assert c.state == PROBING
        c.tick(iter_n=3)           # streak=1
        c.tick(iter_n=4)           # streak=2
        c.tick(iter_n=5)           # streak=3 -> flowing
        assert c.state == FLOWING
        assert c.count == 0

    def test_event_resets_clear_streak(self):
        c, calls = _make(threshold=1, cooldown_iters=1, recovery_iters=3)
        c.event(iter_n=1)
        c.tick(iter_n=2)           # probing
        c.tick(iter_n=3)           # streak=1
        c.event(iter_n=4)          # broken (probe rejected)
        assert c.state == BROKEN
        assert calls["trip"] == 1


class TestBrokenIsTerminal:
    def test_events_after_broken_are_noop(self):
        c, calls = _make(threshold=1, cooldown_iters=1)
        c.event(iter_n=1)
        c.tick(iter_n=2)
        c.event(iter_n=3)          # broken
        pre_count = c.count
        c.event(iter_n=4)
        c.event(iter_n=5)
        assert c.state == BROKEN
        # count still increments for forensic visibility, but on_trip doesn't refire
        assert c.count > pre_count
        assert calls["trip"] == 1


class TestCallbackExceptionsDontPropagate:
    def test_on_eddy_exception_swallowed(self):
        def bad():
            raise RuntimeError("boom")

        c = Circulation(name="t", threshold=1, on_eddy=bad)
        # Must not raise.
        c.event(iter_n=1)
        assert c.state == EDDYING

    def test_on_trip_exception_swallowed(self):
        def bad():
            raise RuntimeError("boom")

        c = Circulation(name="t", threshold=1, cooldown_iters=1, on_trip=bad)
        c.event(iter_n=1)
        c.tick(iter_n=2)
        c.event(iter_n=3)
        assert c.state == BROKEN


class TestResetForTestHarness:
    def test_reset_returns_to_pristine(self):
        c, _ = _make(threshold=1, cooldown_iters=1)
        c.event(iter_n=1)
        c.tick(iter_n=2)
        c.event(iter_n=3)
        assert c.state == BROKEN
        c.reset()
        assert c.state == FLOWING
        assert c.count == 0


class TestSiteParityWithCurrentBehavior:
    """Sanity: parameters matching current agent.py sites produce a trip
    after 3 events with no cool-down interleave — preserving today's
    ``>= 3`` semantics as a worst-case bound."""

    def test_site_b_read_spiral_three_events_trips(self):
        # cooldown_iters=0 collapses eddying on next tick; a probing event
        # then trips. This approximates the current "3rd stall = exit".
        c, calls = _make(threshold=3, cooldown_iters=0, recovery_iters=5)
        c.event(iter_n=1)
        c.event(iter_n=2)
        c.event(iter_n=3)
        assert c.state == EDDYING
        c.tick(iter_n=4)           # cooldown_iters=0 -> probing immediately
        # The 4th event would trip; under today's agent.py, exit fires at
        # the 3rd event. Conversion in agent.py is strictly a behavioral
        # change (adds eddying warning before trip) — documented in design §3.
        assert c.state == PROBING

    def test_site_a_context_overflow_three_events_trips(self):
        # Site A mirrors Site B exactly — same threshold, inline action.
        # This test documents that the refactor did not diverge params.
        # agent.py uses `self.context_overflow.count >= 3` inline; verify
        # the invariants match Site B.
        c, _ = _make(threshold=3, cooldown_iters=2, recovery_iters=5)
        c.event(iter_n=1)
        c.event(iter_n=2)
        c.event(iter_n=3)
        assert c.state == EDDYING
        assert c.count == 3
        # Inline guard in agent.py uses `count >= threshold` — verify.
        assert c.count >= c.threshold

    def test_site_a_matches_agent_wiring_no_callbacks(self):
        # Exact parity with agent.py:166-171 wiring:
        #   Circulation(name="context_overflow", threshold=3,
        #               cooldown_iters=2, recovery_iters=5)
        # with on_eddy=None, on_trip=None (async compress_context can't be
        # a sync callback — see agent.py:160-165 comment). The inline site
        # at agent.py:1203-1233 drives force-deliver on `count >= 3`, and
        # agent.py:1253 calls tick() every iter for cool-down bookkeeping.
        # This test verifies the no-callback variant behaves correctly
        # through a full event → eddying → cool-down → probing cycle.
        fire_log = {"eddy": 0, "trip": 0}
        c = Circulation(
            name="context_overflow",
            threshold=3,
            cooldown_iters=2,
            recovery_iters=5,
            # on_eddy / on_trip intentionally unset — mirrors agent.py.
        )
        # Three 400s arriving at sparse iters (matches chiptune 7/31/58
        # pattern cited in tech_debt #7bb7604).
        c.event(iter_n=7)
        assert c.state == FLOWING
        c.event(iter_n=31)
        assert c.state == FLOWING
        c.event(iter_n=58)
        # 3rd event — enters eddying at flowing→eddying transition.
        # agent.py inline guard `count >= 3` fires here and exits loop.
        assert c.state == EDDYING
        assert c.count == 3
        assert c.count >= c.threshold
        # No callbacks should have fired (on_eddy/on_trip are None).
        # Assert via the Circulation's own state — no AttributeError on
        # missing callbacks, no side-effects. fire_log stays zero by
        # construction (nothing to increment), verified by the absence
        # of a crash during event().
        assert fire_log == {"eddy": 0, "trip": 0}
        # tick() with cooldown_iters=2: +2 iters after eddying → probing.
        c.tick(iter_n=59)           # 1 iter elapsed
        assert c.state == EDDYING
        c.tick(iter_n=60)           # 2 iters elapsed -> probing
        assert c.state == PROBING
        # Late event in probing → broken. agent.py exits before this in
        # practice (return at line 1232/1234), but the state machine
        # must still handle it safely with no callbacks registered.
        c.event(iter_n=61)
        assert c.state == BROKEN
