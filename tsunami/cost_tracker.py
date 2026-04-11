"""Cost tracking — per-model USD costs from token counts.

Tracks input/output tokens per model, calculates USD cost,
formats summaries, and persists session costs to disk.

For local models, cost is $0 but token tracking is still useful
for understanding context burn rate.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("tsunami.cost_tracker")

# --- Pricing tiers ($ per million tokens) ---
# ts
PRICING = {
    # Anthropic models
    "haiku-4-5":  {"input": 1.0, "output": 5.0},
    "sonnet-4-6": {"input": 3.0, "output": 15.0},
    "sonnet-4-5": {"input": 3.0, "output": 15.0},
    "opus-4-6":   {"input": 5.0, "output": 25.0},
    "opus-4-5":   {"input": 5.0, "output": 25.0},
    "opus-4-1":   {"input": 15.0, "output": 75.0},
    "opus-4":     {"input": 15.0, "output": 75.0},
    # Local models — free
    "local":      {"input": 0.0, "output": 0.0},
}


def _get_pricing(model: str) -> dict:
    """Get pricing for a model name. Falls back to local (free)."""
    model_lower = model.lower()
    for key, price in PRICING.items():
        if key in model_lower:
            return price
    return PRICING["local"]


def tokens_to_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost from token counts."""
    price = _get_pricing(model)
    return (
        (input_tokens / 1_000_000) * price["input"]
        + (output_tokens / 1_000_000) * price["output"]
    )


@dataclass
class ModelUsage:
    """Per-model usage accumulator."""
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    cost_usd: float = 0.0
    total_latency_ms: float = 0.0


@dataclass
class CostTracker:
    """Session-level cost tracking."""
    session_id: str = ""
    start_time: float = field(default_factory=time.time)
    model_usage: dict[str, ModelUsage] = field(default_factory=dict)

    def record(self, model: str, input_tokens: int, output_tokens: int,
               latency_ms: float = 0):
        """Record a single LLM call."""
        if model not in self.model_usage:
            self.model_usage[model] = ModelUsage()
        mu = self.model_usage[model]
        mu.input_tokens += input_tokens
        mu.output_tokens += output_tokens
        mu.calls += 1
        mu.total_latency_ms += latency_ms
        mu.cost_usd += tokens_to_usd(model, input_tokens, output_tokens)

    @property
    def total_cost_usd(self) -> float:
        return sum(mu.cost_usd for mu in self.model_usage.values())

    @property
    def total_tokens(self) -> int:
        return sum(mu.input_tokens + mu.output_tokens for mu in self.model_usage.values())

    @property
    def total_input_tokens(self) -> int:
        return sum(mu.input_tokens for mu in self.model_usage.values())

    @property
    def total_output_tokens(self) -> int:
        return sum(mu.output_tokens for mu in self.model_usage.values())

    @property
    def total_calls(self) -> int:
        return sum(mu.calls for mu in self.model_usage.values())

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def format_cost(self, cost: float) -> str:
        """Format USD cost — show 2 decimal places for >$0.50, 4 for smaller."""
        if cost > 0.50:
            return f"${cost:.2f}"
        return f"${cost:.4f}"

    def format_duration(self, seconds: float) -> str:
        """Format duration as Xm Ys."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"

    def format_summary(self) -> str:
        """Format a complete cost summary (production pattern)."""
        lines = [
            f"Total cost:     {self.format_cost(self.total_cost_usd)}",
            f"Total tokens:   {self.total_tokens:,} ({self.total_input_tokens:,} in, {self.total_output_tokens:,} out)",
            f"Total calls:    {self.total_calls}",
            f"Duration:       {self.format_duration(self.elapsed_seconds)}",
        ]

        if len(self.model_usage) > 1:
            lines.append("Usage by model:")
            for model, mu in sorted(self.model_usage.items()):
                lines.append(
                    f"  {model}: {mu.input_tokens:,} in, {mu.output_tokens:,} out, "
                    f"{mu.calls} calls ({self.format_cost(mu.cost_usd)})"
                )

        return "\n".join(lines)

    def save(self, workspace_dir: str):
        """Persist session costs to disk."""
        costs_dir = Path(workspace_dir) / ".costs"
        costs_dir.mkdir(parents=True, exist_ok=True)

        record = {
            "session_id": self.session_id,
            "timestamp": time.time(),
            "elapsed_seconds": self.elapsed_seconds,
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_calls": self.total_calls,
            "model_usage": {
                model: {
                    "input_tokens": mu.input_tokens,
                    "output_tokens": mu.output_tokens,
                    "calls": mu.calls,
                    "cost_usd": mu.cost_usd,
                }
                for model, mu in self.model_usage.items()
            },
        }

        costs_file = costs_dir / "sessions.jsonl"
        with open(costs_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        log.info(f"Saved session costs: {self.format_cost(self.total_cost_usd)}, {self.total_tokens:,} tokens")

    @staticmethod
    def load_history(workspace_dir: str, n: int = 10) -> list[dict]:
        """Load last N session cost records."""
        costs_file = Path(workspace_dir) / ".costs" / "sessions.jsonl"
        if not costs_file.exists():
            return []
        try:
            lines = costs_file.read_text().strip().split("\n")
            return [json.loads(l) for l in lines[-n:] if l.strip()]
        except Exception:
            return []
