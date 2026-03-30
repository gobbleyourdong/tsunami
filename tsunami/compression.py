"""Context compression — prevent context window overflow.

When the conversation grows too long, compress older messages
into a summary. The file system preserves the full history;
the conversation context holds the working set.

Arc.txt: "Context compression happens automatically when token
limits are reached. This means long conversations get compacted —
information can be lost. This is why I save aggressively."
"""

from __future__ import annotations

import logging

from .model import LLMModel
from .state import AgentState, Message

log = logging.getLogger("tsunami.compression")

# Rough token estimate: 1 token ≈ 4 chars for English text
CHARS_PER_TOKEN = 4


def estimate_tokens(state: AgentState) -> int:
    """Estimate total tokens in the conversation."""
    total_chars = sum(len(m.content) for m in state.conversation)
    if state.plan:
        total_chars += len(state.plan.summary())
    return total_chars // CHARS_PER_TOKEN


def needs_compression(state: AgentState, max_tokens: int = 32000) -> bool:
    """Check if context compression is needed."""
    return estimate_tokens(state) > max_tokens


async def compress_context(state: AgentState, model: LLMModel,
                           max_tokens: int = 32000, keep_recent: int = 10):
    """Compress older messages into a summary while preserving recent context.

    Strategy:
    1. Keep the system prompt (message 0)
    2. Keep the user's original request (message 1)
    3. Compress everything between message 1 and the last `keep_recent` messages
    4. Keep the last `keep_recent` messages intact
    """
    if not needs_compression(state, max_tokens):
        return

    total = len(state.conversation)
    if total <= keep_recent + 2:
        return  # Not enough messages to compress

    # Messages to compress: everything between the first 2 and last keep_recent
    compress_start = 2
    compress_end = total - keep_recent

    if compress_end <= compress_start:
        return

    to_compress = state.conversation[compress_start:compress_end]
    log.info(f"Compressing {len(to_compress)} messages (keeping first 2 + last {keep_recent})")

    # Build a summary request
    summary_lines = []
    error_lines = []
    for m in to_compress:
        prefix = m.role.upper()
        # Preserve error messages verbatim (Manus: leave wrong turns visible)
        if "ERROR" in m.content or "error" in m.content[:100]:
            error_lines.append(f"[{prefix}] {m.content[:300]}")
        # Truncate very long messages for the summary input
        content = m.content[:500]
        summary_lines.append(f"[{prefix}] {content}")

    # Append errors at the end so they survive compression
    if error_lines:
        summary_lines.append("\n[ERRORS TO REMEMBER]\n" + "\n".join(error_lines))

    summary_text = "\n".join(summary_lines)

    try:
        response = await model.generate(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a conversation compressor. Summarize the following agent "
                        "conversation history into a concise summary that preserves: "
                        "(1) key decisions made, (2) important findings/results, "
                        "(3) errors encountered and how they were resolved, "
                        "(4) current progress toward the goal. "
                        "Be factual and specific. Include file paths, URLs, and data points. "
                        "Output only the summary, no preamble."
                    ),
                },
                {"role": "user", "content": summary_text},
            ],
        )

        summary = response.content
        if not summary:
            summary = f"[Compressed {len(to_compress)} messages — summary generation failed]"

    except Exception as e:
        log.warning(f"Compression LLM call failed: {e}")
        # Fallback: mechanical summary
        tool_calls = [m for m in to_compress if m.tool_call]
        errors = [m for m in to_compress if m.role == "tool_result" and "ERROR" in m.content]
        summary = (
            f"[Compressed {len(to_compress)} messages: "
            f"{len(tool_calls)} tool calls, {len(errors)} errors]"
        )

    # Replace compressed messages with the summary
    compressed_msg = Message(
        role="system",
        content=f"[CONTEXT COMPRESSED]\n{summary}",
    )

    state.conversation = (
        state.conversation[:compress_start]
        + [compressed_msg]
        + state.conversation[compress_end:]
    )

    new_tokens = estimate_tokens(state)
    log.info(f"Compressed context: {len(to_compress)} messages → 1 summary ({new_tokens} est. tokens)")
