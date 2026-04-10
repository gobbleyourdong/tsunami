"""Time-based microcompact — clear cold tool results after cache expiry.

When the gap since the last assistant message exceeds a threshold,
old tool results are content-cleared (replaced with a short marker).

This recognizes that after a pause (e.g., user went AFK), the LLM's
prompt cache has expired anyway, so we might as well shrink context
before the next API call — saving tokens without losing structure.

Unlike snip (removes messages) or compress (LLM summary), microcompact
only clears the CONTENT of tool results while keeping the message
structure intact. The model still knows which tools ran.
"""

from __future__ import annotations

import logging
import time

from .state import AgentState, Message
from .tool_result_storage import TOOL_RESULT_CLEARED_MESSAGE

log = logging.getLogger("tsunami.microcompact")

# Default gap threshold in seconds before tool results are considered "cold"
# Tsunami uses 60 minutes (matching server prompt cache TTL).
# We use 10 minutes for local models (no server cache to worry about).
DEFAULT_GAP_THRESHOLD_SECONDS = 600  # 10 minutes
DEFAULT_KEEP_RECENT = 5  # always keep last N tool results


def _estimate_chars_freed(messages: list[Message], indices: set[int]) -> int:
    """Estimate characters freed by clearing the given message indices."""
    return sum(
        len(messages[i].content) - len(TOOL_RESULT_CLEARED_MESSAGE)
        for i in indices
        if len(messages[i].content) > len(TOOL_RESULT_CLEARED_MESSAGE)
    )


def microcompact_if_needed(
    state: AgentState,
    gap_threshold: float = DEFAULT_GAP_THRESHOLD_SECONDS,
    keep_recent: int = DEFAULT_KEEP_RECENT,
) -> int:
    """Clear cold tool results if enough time has passed.

    Returns number of characters freed (0 if nothing cleared).

    Only triggers when the gap between the last assistant message and
    now exceeds gap_threshold. This means the prompt cache is likely
    expired, so clearing old results saves tokens without cache loss.
    """
    if len(state.conversation) < 3:
        return 0

    # Find the last assistant message timestamp
    last_assistant_time = 0.0
    for m in reversed(state.conversation):
        if m.role == "assistant":
            last_assistant_time = m.timestamp
            break

    if last_assistant_time == 0:
        return 0

    # Check if the gap exceeds threshold
    gap_seconds = time.time() - last_assistant_time
    if gap_seconds < gap_threshold:
        return 0  # Cache still warm

    # Find tool_result messages eligible for clearing
    # Skip: system (0), user (1), last keep_recent tool results, errors
    tool_result_indices: list[int] = []
    for i, m in enumerate(state.conversation):
        if m.role == "tool_result":
            tool_result_indices.append(i)

    if len(tool_result_indices) <= keep_recent:
        return 0  # Not enough to clear

    # Keep the last keep_recent, clear the rest
    to_clear = tool_result_indices[:-keep_recent] if keep_recent > 0 else tool_result_indices

    chars_freed = 0
    cleared_count = 0
    for idx in to_clear:
        m = state.conversation[idx]
        # Skip already-cleared messages
        if TOOL_RESULT_CLEARED_MESSAGE in m.content:
            continue
        # Skip errors (valuable context)
        if "ERROR" in m.content:
            continue
        # Skip short messages (not worth clearing)
        if len(m.content) <= len(TOOL_RESULT_CLEARED_MESSAGE) + 50:
            continue

        old_len = len(m.content)
        # Preserve tool name prefix for structure
        prefix = m.content.split("]")[0] + "]" if "]" in m.content[:50] else ""
        state.conversation[idx] = Message(
            role=m.role,
            content=f"{prefix} {TOOL_RESULT_CLEARED_MESSAGE}",
            tool_call=m.tool_call,
            timestamp=m.timestamp,
        )
        chars_freed += old_len - len(state.conversation[idx].content)
        cleared_count += 1

    if cleared_count > 0:
        log.info(
            f"Microcompact: cleared {cleared_count} cold tool results "
            f"(gap={gap_seconds:.0f}s, freed ~{chars_freed // 4} tokens)"
        )

    return chars_freed
