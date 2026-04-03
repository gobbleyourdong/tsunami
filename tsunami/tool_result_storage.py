"""Tool result persistence — large results go to disk, smart previews stay in context.

Results larger than PERSISTENCE_THRESHOLD get saved to workspace/.context/<hash>.txt.
Only a compact reference + smart preview remains in conversation context.

Smart previews by tool type:
  - file_read: first 10 + last 5 lines (see the shape of the file)
  - shell_exec: last 20 lines (recent output matters most)
  - default: first N lines up to PREVIEW_MAX_LINES

This prevents context overflow from large file reads, shell outputs, or search
results while keeping the information accessible via file_read.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("tsunami.tool_result_storage")

# --- Constants ---
PERSISTENCE_THRESHOLD = 500  # chars — results larger than this get persisted
PREVIEW_MAX_LINES = 15  # default max lines kept in context
TOOL_RESULT_CLEARED_MESSAGE = "[Old tool result content cleared]"

# Tools whose output should NEVER be persisted
NO_PERSIST_TOOLS = frozenset({"message_info", "message_ask", "message_result"})

# Tool-specific preview strategies
FILE_READ_HEAD = 10  # first N lines
FILE_READ_TAIL = 5   # last N lines
SHELL_EXEC_TAIL = 20  # last N lines


def _format_size(n: int) -> str:
    """Human-readable byte/char size."""
    if n < 1024:
        return f"{n} chars"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


def _content_hash(content: str) -> str:
    """Short hash of content for dedup-friendly filenames."""
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def _count_lines(content: str) -> int:
    """Count lines in content."""
    return content.count("\n") + (1 if content and not content.endswith("\n") else 0)


def generate_file_read_preview(content: str) -> str:
    """Smart preview for file_read: first 10 + last 5 lines.

    Shows the top of the file (imports, types, structure) and
    the bottom (recent additions, exports). Skips the middle.
    """
    lines = content.splitlines(keepends=True)
    total = len(lines)

    if total <= FILE_READ_HEAD + FILE_READ_TAIL:
        return content  # small enough to keep everything

    head = lines[:FILE_READ_HEAD]
    tail = lines[-FILE_READ_TAIL:]
    skipped = total - FILE_READ_HEAD - FILE_READ_TAIL

    return (
        "".join(head)
        + f"\n... ({skipped} lines omitted) ...\n\n"
        + "".join(tail)
    )


def generate_shell_exec_preview(content: str) -> str:
    """Smart preview for shell_exec: last 20 lines.

    Shell output is append-only — the most recent lines contain
    the result, errors, or final status.
    """
    lines = content.splitlines(keepends=True)
    total = len(lines)

    if total <= SHELL_EXEC_TAIL:
        return content

    tail = lines[-SHELL_EXEC_TAIL:]
    skipped = total - SHELL_EXEC_TAIL

    return f"... ({skipped} lines omitted) ...\n\n" + "".join(tail)


def generate_default_preview(content: str, max_lines: int = PREVIEW_MAX_LINES) -> str:
    """Default preview: first N lines."""
    lines = content.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return content

    head = lines[:max_lines]
    skipped = len(lines) - max_lines
    return "".join(head) + f"\n... ({skipped} lines omitted) ..."


def generate_preview(content: str, tool_name: str = "") -> str:
    """Generate a smart preview based on tool type.

    Returns the preview text appropriate for the tool.
    """
    if tool_name == "file_read":
        return generate_file_read_preview(content)
    elif tool_name == "shell_exec":
        return generate_shell_exec_preview(content)
    else:
        return generate_default_preview(content)


def persist_tool_result(
    tool_name: str,
    content: str,
    workspace_dir: str,
    session_id: str = "",
) -> dict | None:
    """Persist a large tool result to disk if it exceeds the threshold.

    Returns a dict with {filepath, preview, line_count, original_size} if persisted,
    or None if the result is small enough to keep in context.
    """
    if tool_name in NO_PERSIST_TOOLS:
        return None

    if len(content) <= PERSISTENCE_THRESHOLD:
        return None

    # Create storage directory
    context_dir = Path(workspace_dir) / ".context"
    context_dir.mkdir(parents=True, exist_ok=True)

    # Hash-based filename for dedup
    content_hash = _content_hash(content)
    filename = f"{content_hash}.txt"
    filepath = context_dir / filename

    # Write full result to disk (skip if identical content already exists)
    if not filepath.exists():
        filepath.write_text(content)

    # Generate tool-specific preview
    preview = generate_preview(content, tool_name)
    line_count = _count_lines(content)

    log.info(f"Persisted {tool_name} result ({line_count} lines, {_format_size(len(content))}) -> .context/{filename}")

    return {
        "filepath": str(filepath),
        "relative": f".context/{filename}",
        "preview": preview,
        "line_count": line_count,
        "original_size": len(content),
    }


def build_persisted_result_message(tool_name: str, result: dict) -> str:
    """Build the compact in-context message for a persisted tool result.

    Format: 1-line reference + smart preview.
    """
    ref_line = f"[{result['line_count']} lines ({_format_size(result['original_size'])}) -> {result['relative']}]"
    return f"{ref_line}\n{result['preview']}"


def maybe_persist(
    tool_name: str,
    content: str,
    workspace_dir: str,
    session_id: str = "",
) -> str:
    """Check if a tool result should be persisted, and return the appropriate content.

    If the result is large enough, persists to disk and returns a compact
    reference + smart preview. Otherwise, returns the original content unchanged.
    """
    result = persist_tool_result(tool_name, content, workspace_dir, session_id)
    if result is None:
        return content
    return build_persisted_result_message(tool_name, result)
