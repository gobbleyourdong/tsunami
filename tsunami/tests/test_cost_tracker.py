"""Tests for cost tracking."""

import json
import os
import tempfile
import pytest

from tsunami.cost_tracker import (
    CostTracker,
    ModelUsage,
    tokens_to_usd,
    _get_pricing,
    PRICING,
)


class TestTokensToUSD:
    """Verify USD cost calculation from token counts."""

    def test_local_model_free(self):
        assert tokens_to_usd("qwen3.5-27b", 1_000_000, 1_000_000) == 0.0

    def test_sonnet_pricing(self):
        # 1M input at $3/M + 1M output at $15/M = $18
        cost = tokens_to_usd("sonnet-4-6", 1_000_000, 1_000_000)
        assert cost == 18.0

    def test_opus_pricing(self):
        # 1M input at $5/M + 1M output at $25/M = $30
        cost = tokens_to_usd("opus-4-6", 1_000_000, 1_000_000)
        assert cost == 30.0

    def test_haiku_pricing(self):
        # 1M input at $1/M + 1M output at $5/M = $6
        cost = tokens_to_usd("haiku-4-5", 1_000_000, 1_000_000)
        assert cost == 6.0

    def test_small_usage(self):
        # 1000 tokens at sonnet pricing
        cost = tokens_to_usd("sonnet-4-5", 1000, 500)
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert abs(cost - expected) < 1e-10

    def test_zero_tokens(self):
        assert tokens_to_usd("opus-4-6", 0, 0) == 0.0

    def test_unknown_model_is_free(self):
        assert tokens_to_usd("some-random-model", 1_000_000, 1_000_000) == 0.0


class TestGetPricing:
    """Model name → pricing tier resolution."""

    def test_exact_match(self):
        p = _get_pricing("sonnet-4-6")
        assert p["input"] == 3.0

    def test_substring_match(self):
        p = _get_pricing("claude-opus-4-6-20260301")
        assert p["input"] == 5.0

    def test_case_insensitive(self):
        p = _get_pricing("Sonnet-4-6")
        assert p["input"] == 3.0

    def test_unknown_defaults_to_local(self):
        p = _get_pricing("tsunami-local")
        assert p["input"] == 0.0
        assert p["output"] == 0.0


class TestCostTracker:
    """Session-level cost accumulation."""

    def test_record_single_call(self):
        ct = CostTracker()
        ct.record("qwen3.5-27b", 5000, 1000)
        assert ct.total_tokens == 6000
        assert ct.total_input_tokens == 5000
        assert ct.total_output_tokens == 1000
        assert ct.total_calls == 1
        assert ct.total_cost_usd == 0.0  # local model

    def test_record_multiple_models(self):
        ct = CostTracker()
        ct.record("qwen3.5-27b", 5000, 1000)
        ct.record("sonnet-4-6", 10000, 2000)
        assert ct.total_calls == 2
        assert ct.total_tokens == 18000
        assert len(ct.model_usage) == 2

    def test_accumulates_per_model(self):
        ct = CostTracker()
        ct.record("qwen3.5-27b", 5000, 1000)
        ct.record("qwen3.5-27b", 3000, 500)
        assert ct.total_calls == 2
        assert ct.model_usage["qwen3.5-27b"].input_tokens == 8000
        assert ct.model_usage["qwen3.5-27b"].output_tokens == 1500

    def test_cost_accumulates(self):
        ct = CostTracker()
        ct.record("sonnet-4-6", 1_000_000, 0)
        ct.record("sonnet-4-6", 1_000_000, 0)
        assert ct.total_cost_usd == 6.0  # 2M input at $3/M

    def test_format_cost_small(self):
        ct = CostTracker()
        assert ct.format_cost(0.001) == "$0.0010"

    def test_format_cost_large(self):
        ct = CostTracker()
        assert ct.format_cost(12.345) == "$12.35"

    def test_format_duration(self):
        ct = CostTracker()
        assert ct.format_duration(45) == "45s"
        assert ct.format_duration(125) == "2m 5s"

    def test_format_summary(self):
        ct = CostTracker()
        ct.record("qwen3.5-27b", 50000, 10000, latency_ms=500)
        summary = ct.format_summary()
        assert "Total cost:" in summary
        assert "Total tokens:" in summary
        assert "60,000" in summary

    def test_format_summary_multi_model(self):
        ct = CostTracker()
        ct.record("qwen3.5-27b", 5000, 1000)
        ct.record("sonnet-4-6", 10000, 2000)
        summary = ct.format_summary()
        assert "Usage by model:" in summary
        assert "qwen3.5-27b" in summary
        assert "sonnet-4-6" in summary


class TestCostTrackerPersistence:
    """Save and load session costs."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_save_creates_file(self):
        ct = CostTracker(session_id="test_session")
        ct.record("qwen3.5-27b", 5000, 1000)
        ct.save(self.tmpdir)
        costs_file = os.path.join(self.tmpdir, ".costs", "sessions.jsonl")
        assert os.path.exists(costs_file)

    def test_save_valid_json(self):
        ct = CostTracker(session_id="test_session")
        ct.record("qwen3.5-27b", 5000, 1000)
        ct.save(self.tmpdir)
        costs_file = os.path.join(self.tmpdir, ".costs", "sessions.jsonl")
        with open(costs_file) as f:
            record = json.loads(f.readline())
        assert record["session_id"] == "test_session"
        assert record["total_tokens"] == 6000

    def test_load_history(self):
        ct = CostTracker(session_id="s1")
        ct.record("qwen3.5-27b", 5000, 1000)
        ct.save(self.tmpdir)

        ct2 = CostTracker(session_id="s2")
        ct2.record("sonnet-4-6", 10000, 2000)
        ct2.save(self.tmpdir)

        history = CostTracker.load_history(self.tmpdir)
        assert len(history) == 2
        assert history[0]["session_id"] == "s1"
        assert history[1]["session_id"] == "s2"

    def test_load_history_empty(self):
        history = CostTracker.load_history(self.tmpdir)
        assert history == []

    def test_multiple_saves_append(self):
        for i in range(5):
            ct = CostTracker(session_id=f"s{i}")
            ct.record("local", 1000, 100)
            ct.save(self.tmpdir)
        history = CostTracker.load_history(self.tmpdir)
        assert len(history) == 5
