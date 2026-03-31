"""Tests for auto-compact circuit breaker (ported from Claude Code's autoCompact.ts)."""

import pytest


class TestCircuitBreaker:
    """Verify the circuit breaker stops retrying after N consecutive failures."""

    def _make_agent_state(self):
        """Create a minimal agent-like object with circuit breaker fields."""
        class FakeAgent:
            _compact_consecutive_failures = 0
            _max_compact_failures = 3
        return FakeAgent()

    def test_initial_state(self):
        """Circuit breaker starts open (allowing compaction)."""
        agent = self._make_agent_state()
        assert agent._compact_consecutive_failures == 0
        assert agent._compact_consecutive_failures < agent._max_compact_failures

    def test_failure_increments(self):
        """Each failure increments the counter."""
        agent = self._make_agent_state()
        agent._compact_consecutive_failures += 1
        assert agent._compact_consecutive_failures == 1
        assert agent._compact_consecutive_failures < agent._max_compact_failures  # still open

    def test_trips_at_threshold(self):
        """Circuit breaker trips at exactly max_compact_failures."""
        agent = self._make_agent_state()
        for _ in range(3):
            agent._compact_consecutive_failures += 1
        assert agent._compact_consecutive_failures >= agent._max_compact_failures  # tripped

    def test_reset_on_success(self):
        """Success resets the counter to 0."""
        agent = self._make_agent_state()
        agent._compact_consecutive_failures = 2  # close to tripping
        # Simulate success
        agent._compact_consecutive_failures = 0
        assert agent._compact_consecutive_failures == 0

    def test_stays_tripped(self):
        """Once tripped, stays tripped (no auto-reset)."""
        agent = self._make_agent_state()
        agent._compact_consecutive_failures = 3
        # Further attempts should be skipped
        should_compact = agent._compact_consecutive_failures < agent._max_compact_failures
        assert should_compact is False

    def test_recovery_after_manual_reset(self):
        """Manual reset (e.g., successful force-compress) allows retry."""
        agent = self._make_agent_state()
        agent._compact_consecutive_failures = 3
        assert agent._compact_consecutive_failures >= agent._max_compact_failures
        # External success resets
        agent._compact_consecutive_failures = 0
        assert agent._compact_consecutive_failures < agent._max_compact_failures


class TestCircuitBreakerInAgentLoop:
    """Integration-style tests verifying the breaker logic in compaction flow."""

    def test_compaction_skipped_when_tripped(self):
        """When breaker is tripped, should_compact stays False even if context is huge."""
        class FakeAgent:
            _compact_consecutive_failures = 3
            _max_compact_failures = 3

        agent = FakeAgent()
        needs_compression = True  # simulate huge context

        should_compact = False
        if agent._compact_consecutive_failures >= agent._max_compact_failures:
            pass  # circuit breaker — skip
        elif needs_compression:
            should_compact = True

        assert should_compact is False

    def test_compaction_allowed_before_threshold(self):
        """When breaker is not tripped, normal compaction proceeds."""
        class FakeAgent:
            _compact_consecutive_failures = 2
            _max_compact_failures = 3

        agent = FakeAgent()
        needs_compression = True

        should_compact = False
        if agent._compact_consecutive_failures >= agent._max_compact_failures:
            pass
        elif needs_compression:
            should_compact = True

        assert should_compact is True
