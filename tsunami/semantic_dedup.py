"""Semantic deduplication — collapse repeated content before compression.

Runs BEFORE fast_prune and importance scoring. Identifies:
1. Duplicate tool results (same content hash) — keep newest only
2. Repeated error messages — collapse to "Error X occurred N times"
3. Repeated file_read of same path — keep only latest read

This saves context tokens that would otherwise be wasted on redundant
information. The dedup is conservative — it only collapses truly
identical or near-identical content.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict

from .state import AgentState, Message
from .tool_result_storage import TOOL_RESULT_CLEARED_MESSAGE

log = logging.getLogger("tsunami.semantic_dedup")

# Hash the first N chars for similarity grouping
HASH_PREFIX_LEN = 200

# Minimum content length to consider for dedup (short messages are cheap)
MIN_DEDUP_LEN = 100


def _content_hash(content: str) -> str:
    """Hash the first 200 chars of content for grouping."""
    prefix = content[:HASH_PREFIX_LEN]
    return hashlib.md5(prefix.encode()).hexdigest()[:10]


def _extract_file_path(content: str) -> str | None:
    """Extract the file path from a file_read tool result."""
    # file_read results start with [file_read] and contain the path
    match = re.match(r'\[file_read\]\s*(.+?)(?:\s*\(|$|\n)', content)
    if match:
        return match.group(1).strip()
    # Also check for path in the content
    match = re.search(r'(?:Reading|Read|file_read)\s+(\S+\.\w+)', content)
    if match:
        return match.group(1)
    return None


def _extract_error_key(content: str) -> str | None:
    """Extract a normalized error key for grouping repeated errors.

    Returns the first line of the error (stripped of timestamps/line numbers)
    to group identical errors together.
    """
    if "ERROR" not in content and "Error" not in content and "error" not in content[:100]:
        return None

    # Get the core error message (first error-containing line)
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "ERROR" in line or "Error" in line or "error" in line:
            # Strip timestamps, line numbers, and tool prefixes
            cleaned = re.sub(r'^\[.*?\]\s*', '', line)  # [tool_name] prefix
            cleaned = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '', cleaned)  # timestamps
            cleaned = re.sub(r'line \d+', 'line N', cleaned)  # line numbers
            cleaned = cleaned.strip()[:120]
            if cleaned:
                return cleaned
    return None


def dedup_messages(state: AgentState, keep_recent: int = 8) -> int:
    """Deduplicate messages in the conversation.

    Runs before fast_prune. Identifies and collapses:
    1. Content-identical tool results (keep newest)
    2. Repeated errors (collapse to count)
    3. Same-path file reads (keep latest)

    Returns number of tokens freed.
    """
    if len(state.conversation) <= keep_recent + 2:
        return 0

    from .compression import estimate_tokens
    before = estimate_tokens(state)

    prunable_end = len(state.conversation) - keep_recent

    # Pass 1: Group by content hash
    hash_groups: dict[str, list[int]] = defaultdict(list)
    # Pass 2: Group file_read by path
    file_read_groups: dict[str, list[int]] = defaultdict(list)
    # Pass 3: Group errors by key
    error_groups: dict[str, list[int]] = defaultdict(list)

    for i in range(2, prunable_end):  # Skip system + user request
        m = state.conversation[i]

        # Skip already-cleared messages
        if TOOL_RESULT_CLEARED_MESSAGE in m.content:
            continue
        # Skip short messages (not worth deduping)
        if len(m.content) < MIN_DEDUP_LEN:
            continue

        # Content hash grouping
        h = _content_hash(m.content)
        hash_groups[h].append(i)

        # File read path grouping
        if m.role == "tool_result" and "[file_read]" in m.content:
            path = _extract_file_path(m.content)
            if path:
                file_read_groups[path].append(i)

        # Error grouping
        if m.role == "tool_result":
            err_key = _extract_error_key(m.content)
            if err_key:
                error_groups[err_key].append(i)

    cleared = 0

    # Dedup 1: Content-identical messages — keep newest (highest index)
    for h, indices in hash_groups.items():
        if len(indices) <= 1:
            continue
        # Keep the newest (last), clear the rest
        to_clear = indices[:-1]
        for i in to_clear:
            m = state.conversation[i]
            state.conversation[i] = Message(
                role=m.role,
                content=f"{TOOL_RESULT_CLEARED_MESSAGE} (duplicate of newer message)",
                tool_call=m.tool_call,
                timestamp=m.timestamp,
            )
            cleared += 1

    # Dedup 2: Same-path file reads — keep latest
    for path, indices in file_read_groups.items():
        if len(indices) <= 1:
            continue
        to_clear = indices[:-1]
        for i in to_clear:
            m = state.conversation[i]
            # Only clear if not already cleared by content dedup
            if TOOL_RESULT_CLEARED_MESSAGE not in state.conversation[i].content or "duplicate" in state.conversation[i].content:
                if "duplicate" not in state.conversation[i].content:
                    state.conversation[i] = Message(
                        role=m.role,
                        content=f"{TOOL_RESULT_CLEARED_MESSAGE} (superseded by newer read of {path})",
                        tool_call=m.tool_call,
                        timestamp=m.timestamp,
                    )
                    cleared += 1

    # Dedup 3: Repeated errors — collapse to count
    for err_key, indices in error_groups.items():
        if len(indices) <= 1:
            continue
        # Keep the newest with a count annotation
        newest_idx = indices[-1]
        newest = state.conversation[newest_idx]
        count = len(indices)

        # Clear all but newest
        to_clear = indices[:-1]
        for i in to_clear:
            m = state.conversation[i]
            if TOOL_RESULT_CLEARED_MESSAGE not in state.conversation[i].content:
                state.conversation[i] = Message(
                    role=m.role,
                    content=TOOL_RESULT_CLEARED_MESSAGE,
                    tool_call=m.tool_call,
                    timestamp=m.timestamp,
                )
                cleared += 1

        # Annotate newest with count (if not already)
        if count > 1 and f"(occurred {count}x)" not in newest.content:
            state.conversation[newest_idx] = Message(
                role=newest.role,
                content=f"[Error occurred {count}x] {newest.content}",
                tool_call=newest.tool_call,
                timestamp=newest.timestamp,
            )

    freed = before - estimate_tokens(state)
    if freed > 0:
        log.info(f"Semantic dedup: cleared {cleared} messages, freed ~{freed} tokens")
    return freed
