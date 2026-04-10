"""Tests for exponential backoff with jitter."""

import pytest
from tsunami.model import get_retry_delay, BASE_DELAY_MS, MAX_DELAY_MS


class TestGetRetryDelay:
    """Verify the backoff formula: base * 2^attempt, capped, with jitter."""

    def test_first_attempt_base_delay(self):
        """Attempt 0 should give ~500ms = 0.5s (plus up to 25% jitter)."""
        delay = get_retry_delay(0)
        assert 0.5 <= delay <= 0.5 * 1.25  # 500ms + up to 125ms jitter

    def test_exponential_growth(self):
        """Each attempt doubles the base delay."""
        delays = [get_retry_delay(i) for i in range(5)]
        # Strip jitter by checking lower bounds
        # attempt 0: 0.5s, 1: 1s, 2: 2s, 3: 4s, 4: 8s
        expected_bases = [0.5, 1.0, 2.0, 4.0, 8.0]
        for delay, base in zip(delays, expected_bases):
            assert delay >= base, f"Attempt delay {delay} should be >= {base}"
            assert delay <= base * 1.25, f"Attempt delay {delay} should be <= {base * 1.25} (25% jitter)"

    def test_cap_at_max_delay(self):
        """Delay should never exceed MAX_DELAY_MS even at high attempts."""
        delay = get_retry_delay(100)  # absurdly high attempt
        max_with_jitter = MAX_DELAY_MS * 1.25 / 1000
        assert delay <= max_with_jitter

    def test_retry_after_header_overrides(self):
        """Retry-After header (in seconds) should override calculated delay."""
        delay = get_retry_delay(0, retry_after="30")
        assert delay == 30

    def test_retry_after_invalid_falls_back(self):
        """Invalid Retry-After should fall back to exponential backoff."""
        delay = get_retry_delay(0, retry_after="not-a-number")
        assert 0.5 <= delay <= 0.5 * 1.25

    def test_retry_after_none_uses_backoff(self):
        """None Retry-After uses normal backoff."""
        delay = get_retry_delay(2, retry_after=None)
        assert 2.0 <= delay <= 2.0 * 1.25

    def test_custom_max_delay(self):
        """Custom max_delay_ms should be respected."""
        delay = get_retry_delay(10, max_delay_ms=2000)
        assert delay <= 2000 * 1.25 / 1000  # 2.5s max

    def test_jitter_is_random(self):
        """Multiple calls should produce different values (jitter)."""
        delays = {get_retry_delay(2) for _ in range(20)}
        assert len(delays) > 1, "Jitter should produce variation"

    def test_delay_always_positive(self):
        """Delay should never be zero or negative."""
        for attempt in range(10):
            assert get_retry_delay(attempt) > 0
