"""Tool result persistence — large results go to disk, previews stay in context.

larger than PERSISTENCE_THRESHOLD, the full output is saved to a file and only
a 2KB preview + filepath reference remains in the conversation context.

This prevents context overflow from large file reads, shell outputs, or search
results while keeping the information accessible via file_read.

Circular read prevention: file_read results are never persisted (they'd create
an infinite loop where the model reads back its own persisted output).
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger("tsunami.tool_result_storage")

# --- Constants ---
PERSISTENCE_THRESHOLD = 2000  # chars — results larger than this get persisted
PREVIEW_SIZE = 2000  # chars — what stays in context
TOOL_RESULT_CLEARED_MESSAGE = "[Old tool result content cleared]"

# Tools whose output should NEVER be persisted (circular read prevention)
NO_PERSIST_TOOLS = frozenset({"file_read", "message_info", "message_ask", "message_result"})


def _format_size(n: int) -> str:
    """Human-readable byte/char size."""
    if n < 1024:
        return f"{n} chars"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


def generate_preview(content: str, max_chars: int = PREVIEW_SIZE) -> tuple[str, bool]:
    """Generate a preview of content, cutting at a newline boundary.

    Returns (preview_text, has_more).
    """
    if len(content) <= max_chars:
        return content, False

    truncated = content[:max_chars]
    # Cut at last newline if reasonably close to limit (>50%)
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars * 0.5:
        cut_point = last_nl
    else:
        cut_point = max_chars

    return content[:cut_point], True


def persist_tool_result(
    tool_name: str,
    content: str,
    workspace_dir: str,
    session_id: str = "",
) -> dict | None:
    """Persist a large tool result to disk if it exceeds the threshold.

    Returns a dict with {filepath, preview, original_size, has_more} if persisted,
    or None if the result is small enough to keep in context.
    """
    # Circular read prevention
    if tool_name in NO_PERSIST_TOOLS:
        return None

    # Size check
    if len(content) <= PERSISTENCE_THRESHOLD:
        return None

    # Create storage directory
    results_dir = Path(workspace_dir) / ".tool_results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    ts = int(time.time() * 1000)
    filename = f"{tool_name}_{ts}.txt"
    filepath = results_dir / filename

    # Write full result to disk
    filepath.write_text(content)

    # Generate preview
    preview, has_more = generate_preview(content)

    log.info(f"Persisted {tool_name} result ({_format_size(len(content))}) → {filepath}")

    return {
        "filepath": str(filepath),
        "preview": preview,
        "original_size": len(content),
        "has_more": has_more,
    }


def build_persisted_result_message(result: dict) -> str:
    """Build the in-context message for a persisted tool result.

    Contains: size info, filepath, and 2KB preview.
    """
    msg = f"[Output too large ({_format_size(result['original_size'])}). "
    msg += f"Full output saved to: {result['filepath']}]\n\n"
    msg += f"Preview (first {_format_size(PREVIEW_SIZE)}):\n"
    msg += result["preview"]
    if result["has_more"]:
        msg += "\n..."
    return msg


def maybe_persist(
    tool_name: str,
    content: str,
    workspace_dir: str,
    session_id: str = "",
) -> str:
    """Check if a tool result should be persisted, and return the appropriate content.

    If the result is large enough, persists to disk and returns a preview message.
    Otherwise, returns the original content unchanged.
    """
    result = persist_tool_result(tool_name, content, workspace_dir, session_id)
    if result is None:
        return content
    return build_persisted_result_message(result)
