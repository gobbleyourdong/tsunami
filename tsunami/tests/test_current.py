"""Tests for current — semantic tension measurement."""

import pytest
from tsunami.current import measure_heuristic, GROUNDED, UNCERTAIN, DRIFTING


class TestMeasureHeuristic:
    """Fast heuristic tension without model calls."""

    def test_grounded_with_citations(self):
        text = "According to Nature [1], the protein folds at 37°C. Published in 2024."
        score = measure_heuristic(text)
        assert score < UNCERTAIN

    def test_grounded_with_url(self):
        text = "The data is available at https://arxiv.org/abs/2401.12345"
        score = measure_heuristic(text)
        assert score < UNCERTAIN

    def test_drifting_with_hedging(self):
        text = "I think probably this might be around 50 million percent."
        score = measure_heuristic(text)
        assert score > GROUNDED

    def test_drifting_with_vague_source(self):
        text = "According to some studies, research indicates approximately 5000 billion things."
        score = measure_heuristic(text)
        assert score > GROUNDED

    def test_empty_text(self):
        assert measure_heuristic("") == 0.5

    def test_short_text_more_suspicious(self):
        short = measure_heuristic("Yes.")
        long = measure_heuristic("The answer is yes, based on the documented evidence from multiple peer-reviewed sources.")
        assert short >= long

    def test_range_0_to_1(self):
        for text in ["", "hello", "I think probably maybe", "According to Nature [1]"]:
            score = measure_heuristic(text)
            assert 0.0 <= score <= 1.0


class TestThresholds:
    """Threshold constants are sane."""

    def test_ordering(self):
        assert GROUNDED < UNCERTAIN < DRIFTING

    def test_grounded_is_low(self):
        assert GROUNDED < 0.2

    def test_drifting_is_high(self):
        assert DRIFTING > 0.5
