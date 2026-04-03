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
from .tool_result_storage import TOOL_RESULT_CLEARED_MESSAGE

log = logging.getLogger("tsunami.compression")

# Compaction prompt with analysis scratchpad pattern:
# The model writes <analysis> first (thinking through what matters),
# then <summary> (the actual output). We strip <analysis> before
# injecting into context — the model gets better summaries by
# reasoning first, but the reasoning doesn't waste context tokens.
COMPACT_SYSTEM_PROMPT = (
    "CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.\n"
    "Tool calls will be REJECTED and waste your only turn.\n\n"
    "First write an <analysis> section where you think through what's important.\n"
    "Then write a <summary> section with the actual structured summary.\n\n"
    "The <analysis> is your scratchpad — it will be stripped from the output.\n"
    "Only the <summary> content will be kept.\n\n"
    "<summary> must contain these sections:\n"
    "1. Primary Request and Intent: What the user asked for and why\n"
    "2. Key Technical Concepts: Architecture decisions, patterns chosen\n"
    "3. Files and Code Sections: File paths, line numbers, what changed\n"
    "4. Errors and Fixes: What broke and how it was fixed\n"
    "5. All User Messages: Key directives (critical for intent drift detection)\n"
    "6. Pending Tasks: What still needs to be done\n"
    "7. Current Work: What was being worked on RIGHT BEFORE this summary\n"
    "8. Optional Next Step: Must align with recent explicit user requests\n\n"
    "Be factual and specific. Include file paths, code snippets, and data points.\n"
    "Do NOT include pleasantries, meta-commentary, or filler."
)


def strip_analysis_scratchpad(text: str) -> str:
    """Strip <analysis>...</analysis> from compaction output.

    The model reasons in <analysis> but only <summary> survives into context.
    This gives better summaries without wasting context on reasoning.
    """
    import re
    # Remove analysis block
    text = re.sub(r'<analysis>.*?</analysis>', '', text, flags=re.DOTALL).strip()
    # Extract summary content (remove tags)
    match = re.search(r'<summary>(.*?)</summary>', text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    # If no tags, return as-is (model didn't use the format)
    return text.strip()


# Rough token estimate: 1 token ≈ 4 chars for English text
CHARS_PER_TOKEN = 4

# Autocompact thresholds
AUTOCOMPACT_BUFFER_TOKENS = 13_000  # trigger at context_window - this buffer
WARNING_THRESHOLD_BUFFER = 20_000   # warn when this close to limit


def estimate_tokens(state: AgentState) -> int:
    """Estimate total tokens in the conversation."""
    total_chars = sum(len(m.content) for m in state.conversation)
    if state.plan:
        total_chars += len(state.plan.summary())
    return total_chars // CHARS_PER_TOKEN


def get_autocompact_threshold(context_window: int) -> int:
    """Calculate when autocompact should trigger.

    trigger at context_window - AUTOCOMPACT_BUFFER_TOKENS.
    This leaves enough room for the model to generate a response + summary.
    """
    return context_window - AUTOCOMPACT_BUFFER_TOKENS


def calculate_token_warning(token_count: int, context_window: int) -> dict:
    """Calculate token usage warning state.

     Returns a dict with:
    - percent_left: how much context remains (0-100)
    - needs_compact: should autocompact trigger?
    - needs_warning: should we warn the user?
    """
    threshold = get_autocompact_threshold(context_window)
    percent_left = max(0, round(((threshold - token_count) / max(threshold, 1)) * 100))

    return {
        "percent_left": percent_left,
        "needs_compact": token_count >= threshold,
        "needs_warning": token_count >= (context_window - WARNING_THRESHOLD_BUFFER),
        "token_count": token_count,
        "threshold": threshold,
        "context_window": context_window,
    }


def needs_compression(state: AgentState, max_tokens: int = 32000) -> bool:
    """Check if context compression is needed."""
    return estimate_tokens(state) > max_tokens


def _message_importance(m: Message, index: int, total: int) -> float:
    """Score a message's importance (0.0 = disposable, 1.0 = critical).

    High importance: user request, plan, types/architecture, errors
    Low importance: verbose tool results, shell output, search results
    """
    content = m.content
    content_lower = content.lower()

    # System + user request are always critical
    if m.role == "system":
        return 1.0
    if m.role == "user":
        return 0.9

    # Errors are important — the agent needs to see what failed
    if "ERROR" in content or "FAIL" in content or "BLOCKED" in content:
        return 0.8

    # Plan updates are architecture — high importance
    if m.role == "assistant" and m.tool_call:
        tc = m.tool_call.get("function", m.tool_call)
        tool_name = tc.get("name", "")
        if tool_name == "plan_update":
            return 0.85
        if tool_name == "message_result":
            return 0.8
        if tool_name == "file_write" and "types.ts" in str(tc.get("arguments", {})):
            return 0.8  # types define the architecture
        if tool_name == "file_write" and "App.tsx" in str(tc.get("arguments", {})):
            return 0.75
        if tool_name in ("file_write", "file_edit"):
            return 0.6
        if tool_name in ("search_web", "generate_image"):
            return 0.5
        if tool_name in ("shell_exec", "match_glob", "match_grep", "file_read"):
            return 0.3

    # Tool results — importance based on content type
    if m.role == "tool_result":
        if len(content) < 100:
            return 0.4  # short results are summaries, keep them
        if "Wrote" in content or "Edited" in content:
            return 0.5
        if "COMPILE ERROR" in content or "RUNTIME ERROR" in content:
            return 0.8
        if "AUTO-SWELL" in content or "AVAILABLE COMPONENTS" in content:
            return 0.6
        # Verbose output — search results, file contents, shell output
        return 0.2

    # System notes — nudges and reminders
    if "STALL" in content or "VERIFICATION" in content:
        return 0.3  # stale after being acted on

    return 0.4  # default


def fast_prune(state: AgentState, keep_recent: int = 8) -> int:
    """Tier 1: Fast prune — drop LOW IMPORTANCE messages first.

    Priority-based: scores each message by importance, prunes the
    least important first regardless of age. Architecture decisions
    survive while verbose tool results get cleared.

    Returns number of tokens freed.
    """
    if len(state.conversation) <= keep_recent + 2:
        return 0

    before = estimate_tokens(state)
    prunable_end = len(state.conversation) - keep_recent
    total = len(state.conversation)

    # Score all prunable messages
    scored = []
    for i in range(2, prunable_end):  # Skip system + user
        m = state.conversation[i]
        if m.role == "tool_result" and not m.tool_call:
            importance = _message_importance(m, i, total)
            scored.append((i, importance, len(m.content)))

    # Sort by importance (lowest first) — prune least important first
    scored.sort(key=lambda x: x[1])

    for i, importance, content_len in scored:
        m = state.conversation[i]
        # Only prune messages with importance < 0.5 and content > 200 chars
        if importance < 0.5 and content_len > 200:
            filepath_line = ""
            if "Full output saved to:" in m.content:
                for line in m.content.split("\n"):
                    if "saved to:" in line:
                        filepath_line = f" | {line.strip()}"
                        break
            state.conversation[i] = Message(
                role=m.role,
                content=f"{TOOL_RESULT_CLEARED_MESSAGE}{filepath_line}",
                tool_call=m.tool_call,
                timestamp=m.timestamp,
            )

    freed = before - estimate_tokens(state)
    if freed > 0:
        log.info(f"Priority prune freed ~{freed} tokens")
    return freed


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
                    "content": COMPACT_SYSTEM_PROMPT,
                },
                {"role": "user", "content": summary_text},
            ],
        )

        raw_summary = response.content
        if not raw_summary:
            summary = f"[Compressed {len(to_compress)} messages — summary generation failed]"
        else:
            # Strip analysis scratchpad — only keep <summary> content
            summary = strip_analysis_scratchpad(raw_summary)
            if not summary:
                summary = raw_summary  # fallback to raw if stripping removed everything

    except Exception as e:
        log.warning(f"Compression LLM call failed: {e}")
        # Fallback: mechanical summary
        tool_calls = [m for m in to_compress if m.tool_call]
        errors = [m for m in to_compress if m.role == "tool_result" and "ERROR" in m.content]
        summary = (
            f"[Compressed {len(to_compress)} messages: "
            f"{len(tool_calls)} tool calls, {len(errors)} errors]"
        )

    # Find the last successful tool call to preserve as a pattern example
    exemplar = None
    for m in reversed(to_compress):
        if m.tool_call and m.role == "assistant":
            import json
            tc = m.tool_call.get("function", m.tool_call)
            tc_json = json.dumps({"name": tc.get("name", ""), "arguments": tc.get("arguments", {})})
            if len(tc_json) < 300:  # Only keep small examples
                exemplar = Message(role="assistant", content=tc_json, tool_call=m.tool_call)
                break

    # Replace compressed messages with summary + exemplar
    compressed_msg = Message(
        role="system",
        content=f"[CONTEXT COMPRESSED]\n{summary}",
    )

    replacement = [compressed_msg]
    if exemplar:
        replacement.append(exemplar)
        replacement.append(Message(role="tool_result", content="[previous result — see summary above]"))

    state.conversation = (
        state.conversation[:compress_start]
        + replacement
        + state.conversation[compress_end:]
    )

    # Post-compact cleanup: reset stale caches
    state.error_counts.clear()  # Old error tracking is stale after compression

    new_tokens = estimate_tokens(state)
    log.info(f"Compressed context: {len(to_compress)} messages → 1 summary ({new_tokens} est. tokens)")
