"""Tests for model fallback on consecutive overload errors."""

import pytest

from tsunami.model_fallback import (
    FallbackState,
    FallbackTriggeredError,
    OVERLOAD_CODES,
    DEFAULT_MAX_FAILURES,
)


class TestFallbackState:
    """Track consecutive failures and trigger fallback."""

    def test_initial_state(self):
        state = FallbackState(primary_model="qwen-27b", fallback_model="qwen-2b")
        assert state.consecutive_failures == 0
        assert state.is_using_fallback is False
        assert state.current_model == "qwen-27b"

    def test_overload_counts(self):
        state = FallbackState(primary_model="p", fallback_model="f")
        state.record_failure(529)
        assert state.consecutive_failures == 1
        state.record_failure(503)
        assert state.consecutive_failures == 2

    def test_non_overload_doesnt_count(self):
        state = FallbackState(primary_model="p", fallback_model="f")
        result = state.record_failure(400)
        assert result is False
        assert state.consecutive_failures == 0

        result = state.record_failure(500)
        assert result is False
        assert state.consecutive_failures == 0

    def test_triggers_at_threshold(self):
        state = FallbackState(primary_model="p", fallback_model="f", max_failures=3)
        state.record_failure(529)
        state.record_failure(529)
        should_trigger = state.record_failure(529)
        assert should_trigger is True

    def test_no_trigger_without_fallback_model(self):
        state = FallbackState(primary_model="p", fallback_model="")
        state.record_failure(529)
        state.record_failure(529)
        should_trigger = state.record_failure(529)
        assert should_trigger is False

    def test_success_resets(self):
        state = FallbackState(primary_model="p", fallback_model="f")
        state.record_failure(529)
        state.record_failure(529)
        state.record_success()
        assert state.consecutive_failures == 0

    def test_trigger_fallback(self):
        state = FallbackState(primary_model="qwen-27b", fallback_model="qwen-2b")
        model = state.trigger_fallback()
        assert model == "qwen-2b"
        assert state.is_using_fallback is True
        assert state.current_model == "qwen-2b"
        assert state.total_fallbacks == 1

    def test_restore_primary(self):
        state = FallbackState(primary_model="qwen-27b", fallback_model="qwen-2b")
        state.trigger_fallback()
        assert state.current_model == "qwen-2b"
        state.restore_primary()
        assert state.current_model == "qwen-27b"
        assert state.is_using_fallback is False

    def test_multiple_fallbacks(self):
        state = FallbackState(primary_model="p", fallback_model="f")
        state.trigger_fallback()
        state.restore_primary()
        state.trigger_fallback()
        assert state.total_fallbacks == 2

    def test_has_fallback(self):
        assert FallbackState(primary_model="p", fallback_model="f").has_fallback is True
        assert FallbackState(primary_model="p", fallback_model="").has_fallback is False

    def test_format_status_normal(self):
        state = FallbackState(primary_model="qwen-27b")
        assert "qwen-27b" in state.format_status()

    def test_format_status_failing(self):
        state = FallbackState(primary_model="p", fallback_model="f")
        state.record_failure(529)
        status = state.format_status()
        assert "1/" in status

    def test_format_status_fallback(self):
        state = FallbackState(primary_model="p", fallback_model="f")
        state.trigger_fallback()
        status = state.format_status()
        assert "fallback" in status.lower()


class TestFallbackTriggeredError:
    """Exception for model switching."""

    def test_contains_models(self):
        err = FallbackTriggeredError("primary", "fallback")
        assert err.primary_model == "primary"
        assert err.fallback_model == "fallback"
        assert "primary" in str(err)
        assert "fallback" in str(err)


class TestOverloadCodes:
    """Verify which HTTP codes trigger fallback."""

    def test_529_is_overload(self):
        assert 529 in OVERLOAD_CODES

    def test_503_is_overload(self):
        assert 503 in OVERLOAD_CODES

    def test_500_is_not_overload(self):
        assert 500 not in OVERLOAD_CODES

    def test_429_is_not_overload(self):
        """429 (rate limit) handled by retry, not fallback."""
        assert 429 not in OVERLOAD_CODES

    def test_400_is_not_overload(self):
        assert 400 not in OVERLOAD_CODES
