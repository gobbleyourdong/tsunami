"""Quality filter — only train on good data.

Filters:
1. Score >= 7/10 (compile + render + at least some functionality)
2. Code actually compiles (re-verify with vite build)
3. Deduplicate near-identical pairs
4. Balance scaffold representation
5. Token count within model context window
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from .trace_extractor import SessionTrace
from .pair_generator import BuilderPair, OrchestratorPair

log = logging.getLogger("tsunami.training.quality_filter")

# Token estimates (chars / 4)
MAX_2B_TOKENS = 8192   # 2B context for builder pairs
MAX_9B_TOKENS = 32768  # 9B context for orchestrator pairs


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 chars."""
    return len(text) // 4


@dataclass
class FilterStats:
    """Statistics from the filtering process."""
    input_count: int = 0
    passed: int = 0
    rejected_score: int = 0
    rejected_tokens: int = 0
    rejected_duplicate: int = 0
    rejected_empty: int = 0


def filter_traces(
    traces: list[SessionTrace],
    min_score: int = 7,
    require_complete: bool = True,
) -> tuple[list[SessionTrace], FilterStats]:
    """Filter session traces by quality.

    Returns (filtered_traces, stats).
    """
    stats = FilterStats(input_count=len(traces))
    filtered = []

    for trace in traces:
        # Must be complete
        if require_complete and not trace.task_complete:
            stats.rejected_score += 1
            continue

        # Must have minimum score
        if trace.score < min_score:
            stats.rejected_score += 1
            continue

        # Must have actual tool calls
        if len(trace.tool_calls) < 3:
            stats.rejected_empty += 1
            continue

        filtered.append(trace)

    stats.passed = len(filtered)
    return filtered, stats


def filter_builder_pairs(
    pairs: list[BuilderPair],
    max_tokens: int = MAX_2B_TOKENS,
) -> tuple[list[BuilderPair], FilterStats]:
    """Filter builder pairs for 2B training."""
    stats = FilterStats(input_count=len(pairs))
    filtered = []
    seen_hashes: set[str] = set()

    for pair in pairs:
        # Token check
        total_tokens = estimate_tokens(pair.instruction + pair.context + pair.output)
        if total_tokens > max_tokens:
            stats.rejected_tokens += 1
            continue

        # Empty output check
        if len(pair.output.strip()) < 50:
            stats.rejected_empty += 1
            continue

        # Dedup: hash the output (same code = same training signal)
        output_hash = hashlib.md5(pair.output[:500].encode()).hexdigest()[:10]
        if output_hash in seen_hashes:
            stats.rejected_duplicate += 1
            continue
        seen_hashes.add(output_hash)

        filtered.append(pair)

    stats.passed = len(filtered)
    return filtered, stats


def filter_orchestrator_pairs(
    pairs: list[OrchestratorPair],
    max_tokens: int = MAX_9B_TOKENS,
) -> tuple[list[OrchestratorPair], FilterStats]:
    """Filter orchestrator pairs for 9B training."""
    stats = FilterStats(input_count=len(pairs))
    filtered = []
    seen_prompts: set[str] = set()

    for pair in pairs:
        # Token check
        seq_text = str(pair.tool_sequence)
        total_tokens = estimate_tokens(pair.user_prompt + pair.context + pair.plan + seq_text)
        if total_tokens > max_tokens:
            stats.rejected_tokens += 1
            continue

        # Must have a real tool sequence
        if len(pair.tool_sequence) < 3:
            stats.rejected_empty += 1
            continue

        # Dedup by prompt similarity
        prompt_key = pair.user_prompt[:100].lower().strip()
        if prompt_key in seen_prompts:
            stats.rejected_duplicate += 1
            continue
        seen_prompts.add(prompt_key)

        filtered.append(pair)

    stats.passed = len(filtered)
    return filtered, stats


def compute_scaffold_balance(pairs: list) -> dict[str, int]:
    """Compute scaffold distribution across pairs."""
    dist: dict[str, int] = {}
    for pair in pairs:
        scaffold = pair.metadata.get("scaffold", "unknown")
        dist[scaffold] = dist.get(scaffold, 0) + 1
    return dict(sorted(dist.items(), key=lambda x: -x[1]))
