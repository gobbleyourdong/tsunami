"""Tests for smart autocompact threshold (ported from Claude Code's autoCompact.ts)."""

import pytest

from tsunami.compression import (
    get_autocompact_threshold,
    calculate_token_warning,
    AUTOCOMPACT_BUFFER_TOKENS,
    WARNING_THRESHOLD_BUFFER,
)


class TestAutocompactThreshold:
    """Threshold calculation: context_window - buffer."""

    def test_default_buffer(self):
        assert AUTOCOMPACT_BUFFER_TOKENS == 13_000

    def test_threshold_16k_context(self):
        # 16K context - 13K buffer = 3K threshold
        assert get_autocompact_threshold(16_000) == 3_000

    def test_threshold_32k_context(self):
        # 32K context - 13K buffer = 19K threshold
        assert get_autocompact_threshold(32_000) == 19_000

    def test_threshold_128k_context(self):
        # 128K - 13K = 115K
        assert get_autocompact_threshold(128_000) == 115_000

    def test_threshold_200k_context(self):
        # 200K - 13K = 187K
        assert get_autocompact_threshold(200_000) == 187_000


class TestCalculateTokenWarning:
    """Token usage warning state calculation."""

    def test_low_usage_no_warnings(self):
        state = calculate_token_warning(1000, 32_000)
        assert state["needs_compact"] is False
        assert state["needs_warning"] is False
        assert state["percent_left"] > 90

    def test_near_threshold_needs_compact(self):
        threshold = get_autocompact_threshold(32_000)  # 19K
        state = calculate_token_warning(threshold, 32_000)
        assert state["needs_compact"] is True

    def test_above_threshold_needs_compact(self):
        threshold = get_autocompact_threshold(32_000)
        state = calculate_token_warning(threshold + 1000, 32_000)
        assert state["needs_compact"] is True

    def test_below_threshold_no_compact(self):
        threshold = get_autocompact_threshold(32_000)
        state = calculate_token_warning(threshold - 1, 32_000)
        assert state["needs_compact"] is False

    def test_warning_near_limit(self):
        # Warning at context_window - WARNING_THRESHOLD_BUFFER
        state = calculate_token_warning(32_000 - WARNING_THRESHOLD_BUFFER, 32_000)
        assert state["needs_warning"] is True

    def test_no_warning_well_below(self):
        state = calculate_token_warning(1000, 32_000)
        assert state["needs_warning"] is False

    def test_percent_left_full(self):
        state = calculate_token_warning(0, 32_000)
        assert state["percent_left"] == 100

    def test_percent_left_at_threshold(self):
        threshold = get_autocompact_threshold(32_000)
        state = calculate_token_warning(threshold, 32_000)
        assert state["percent_left"] == 0

    def test_percent_left_halfway(self):
        threshold = get_autocompact_threshold(32_000)
        state = calculate_token_warning(threshold // 2, 32_000)
        assert 45 <= state["percent_left"] <= 55  # roughly 50%

    def test_percent_left_never_negative(self):
        state = calculate_token_warning(100_000, 32_000)
        assert state["percent_left"] == 0

    def test_state_contains_all_fields(self):
        state = calculate_token_warning(5000, 32_000)
        assert "percent_left" in state
        assert "needs_compact" in state
        assert "needs_warning" in state
        assert "token_count" in state
        assert "threshold" in state
        assert "context_window" in state

    def test_small_context_window(self):
        # Edge case: context smaller than buffer
        state = calculate_token_warning(1000, 10_000)
        threshold = get_autocompact_threshold(10_000)  # -3000 (negative!)
        # Should still work without crashing
        assert isinstance(state["percent_left"], int)
