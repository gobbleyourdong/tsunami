"""Message snipping — targeted removal of old messages to free tokens.


Unlike full compression (which summarizes everything), snipping selectively
removes the oldest, least-valuable messages while preserving structure.

Strategy:
1. Keep system prompt (index 0) and original user request (index 1)
2. Keep the last N messages (recent context)
3. Remove messages between them, starting from oldest
4. Stop when enough tokens are freed

This is faster than LLM compression and preserves more recent context.
The snipped messages are gone from the conversation (not summarized).
"""

from __future__ import annotations

import logging
from .state import AgentState, Message

log = logging.getLogger("tsunami.snip")

# Characters per token estimate
CHARS_PER_TOKEN = 4


def _estimate_message_tokens(m: Message) -> int:
    return len(m.content) // CHARS_PER_TOKEN


def snip_if_needed(
    state: AgentState,
    target_tokens: int,
    keep_recent: int = 8,
    min_free_tokens: int = 4000,
) -> int:
    """Snip old messages to free tokens.

    Unlike fast_prune (which clears content), this REMOVES entire messages.
    Unlike compress_context (which calls LLM), this is instant.

    Args:
        state: Agent state with conversation
        target_tokens: Token budget — snip until under this limit
        keep_recent: Number of recent messages to always keep
        min_free_tokens: Minimum tokens to free (skip if savings too small)

    Returns:
        Number of tokens freed.
    """
    # Current token estimate
    total_chars = sum(len(m.content) for m in state.conversation)
    current_tokens = total_chars // CHARS_PER_TOKEN

    if current_tokens <= target_tokens:
        return 0  # Already under budget

    # Protected zones: first 2 messages + last keep_recent
    total = len(state.conversation)
    if total <= keep_recent + 2:
        return 0  # Nothing to snip

    snip_start = 2  # After system + user
    snip_end = total - keep_recent

    if snip_end <= snip_start:
        return 0

    # Score messages for removal priority:
    # - tool_result with cleared/pruned content → highest priority (already empty)
    # - tool_result without errors → high priority
    # - assistant without tool_call → medium (reasoning text)
    # - assistant with tool_call → lower (preserves pattern)
    # - messages with errors → lowest (must remember failures)
    scored: list[tuple[int, int]] = []  # (priority, index)
    for i in range(snip_start, snip_end):
        m = state.conversation[i]
        if "[Old tool result content cleared]" in m.content or "[pruned]" in m.content:
            scored.append((0, i))  # Already empty — snip first
        elif m.role == "tool_result" and "ERROR" not in m.content:
            scored.append((1, i))
        elif m.role == "assistant" and not m.tool_call:
            scored.append((2, i))
        elif m.role == "assistant" and m.tool_call:
            scored.append((3, i))
        elif "ERROR" in m.content:
            scored.append((5, i))  # Keep errors as long as possible
        else:
            scored.append((4, i))

    # Sort by priority (lowest = snip first)
    scored.sort()

    # Remove messages until we hit the target
    to_remove: set[int] = set()
    freed_chars = 0
    tokens_needed = current_tokens - target_tokens

    for priority, idx in scored:
        freed_chars += len(state.conversation[idx].content)
        to_remove.add(idx)
        if freed_chars // CHARS_PER_TOKEN >= tokens_needed:
            break

    freed_tokens_est = freed_chars // CHARS_PER_TOKEN
    # Skip if savings are too small AND we don't actually need to free
    if freed_tokens_est < min_free_tokens and freed_tokens_est < tokens_needed:
        return 0

    # Remove messages in reverse order to preserve indices
    state.conversation = [
        m for i, m in enumerate(state.conversation) if i not in to_remove
    ]

    freed_tokens = freed_chars // CHARS_PER_TOKEN
    log.info(f"Snipped {len(to_remove)} messages, freed ~{freed_tokens} tokens")
    return freed_tokens
