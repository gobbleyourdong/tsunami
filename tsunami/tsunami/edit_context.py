"""Edit context extraction — smart snippet loading for safe edits.

When the model wants to edit a file, it often sends a search string
(old_text) that may not match exactly. This module provides fast,
context-aware snippet loading that:

1. Finds the best match location in the file
2. Returns surrounding context lines for verification
3. Handles large files by scanning in chunks
4. Supports both exact and fuzzy matching
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("tsunami.edit_context")

# Scan cap for large files
MAX_SCAN_BYTES = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 8192
CHUNK_OVERLAP = 200  # overlap between chunks to catch cross-boundary matches
DEFAULT_CONTEXT_LINES = 3


def find_in_file(path: str, needle: str, context_lines: int = DEFAULT_CONTEXT_LINES) -> dict | None:
    """Find a string in a file and return it with surrounding context.

    Returns dict with:
    - match_line: 0-indexed line number of the match start
    - match_text: the exact matched text
    - before: context lines before the match
    - after: context lines after the match
    - total_lines: total lines in the file

    Returns None if not found.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None

    try:
        # Size check
        size = p.stat().st_size
        if size > MAX_SCAN_BYTES:
            return _find_in_large_file(path, needle, context_lines)

        content = p.read_text(errors="replace")
    except OSError:
        return None

    # Exact match
    idx = content.find(needle)
    if idx == -1:
        # Try whitespace-normalized match
        idx = _fuzzy_find(content, needle)
        if idx == -1:
            return None

    lines = content.splitlines()
    total_lines = len(lines)

    # Find line number of match
    match_line = content[:idx].count("\n")

    # Calculate needle span in lines
    needle_line_count = needle.count("\n") + 1
    match_end_line = match_line + needle_line_count - 1

    # Extract context
    before_start = max(0, match_line - context_lines)
    after_end = min(total_lines, match_end_line + context_lines + 1)

    before = lines[before_start:match_line]
    match_lines = lines[match_line:match_end_line + 1]
    after = lines[match_end_line + 1:after_end]

    return {
        "match_line": match_line,
        "match_end_line": match_end_line,
        "match_text": "\n".join(match_lines),
        "before": before,
        "after": after,
        "total_lines": total_lines,
    }


def _find_in_large_file(path: str, needle: str, context_lines: int) -> dict | None:
    """Scan a large file in chunks to find needle.

    Uses overlapping chunks to catch matches that span chunk boundaries.
    """
    try:
        with open(path, "r", errors="replace") as f:
            offset = 0
            prev_tail = ""
            line_offset = 0

            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break

                # Prepend overlap from previous chunk
                search_text = prev_tail + chunk

                idx = search_text.find(needle)
                if idx != -1:
                    # Found — now load context
                    # Seek back to get surrounding lines
                    f.seek(0)
                    content = f.read(min(offset + CHUNK_SIZE * 2, MAX_SCAN_BYTES))
                    return find_in_file.__wrapped__(path, needle, context_lines) if hasattr(find_in_file, '__wrapped__') else None

                # Keep tail for overlap
                prev_tail = chunk[-CHUNK_OVERLAP:] if len(chunk) >= CHUNK_OVERLAP else chunk
                line_offset += chunk.count("\n")
                offset += len(chunk)

                if offset >= MAX_SCAN_BYTES:
                    break

    except OSError:
        pass

    return None


def _fuzzy_find(content: str, needle: str) -> int:
    """Find needle in content with whitespace normalization.

    Strips trailing whitespace from each line of both content and needle
    before matching. Returns the index in the ORIGINAL content.
    """
    # Normalize both
    content_lines = content.split("\n")
    needle_lines = needle.split("\n")

    stripped_content = "\n".join(l.rstrip() for l in content_lines)
    stripped_needle = "\n".join(l.rstrip() for l in needle_lines)

    idx = stripped_content.find(stripped_needle)
    if idx == -1:
        return -1

    # Map back to original content position
    # Count characters up to the match in the original
    stripped_before = stripped_content[:idx]
    original_line = stripped_before.count("\n")

    # Find the byte offset of that line in original content
    original_idx = 0
    for i, line in enumerate(content_lines):
        if i == original_line:
            # Add the column offset within the line
            col = idx - len(stripped_before.rsplit("\n", 1)[0]) - 1 if "\n" in stripped_before else idx
            return original_idx + max(0, col)
        original_idx += len(line) + 1  # +1 for \n

    return idx


def get_edit_preview(path: str, old_text: str, new_text: str,
                     context_lines: int = DEFAULT_CONTEXT_LINES) -> str | None:
    """Generate a preview of what an edit would look like.

    Shows the match with context, highlighting the change.
    Returns None if old_text not found.
    """
    result = find_in_file(path, old_text, context_lines)
    if result is None:
        return None

    lines = []
    line_num = result["match_line"] - len(result["before"])

    # Before context
    for line in result["before"]:
        line_num += 1
        lines.append(f"  {line_num:>5} | {line}")

    # Old text (being replaced)
    for line in result["match_text"].split("\n"):
        line_num += 1
        lines.append(f"- {line_num:>5} | {line}")

    # New text (replacement)
    for line in new_text.split("\n"):
        lines.append(f"+       | {line}")

    # After context
    line_num = result["match_end_line"]
    for line in result["after"]:
        line_num += 1
        lines.append(f"  {line_num:>5} | {line}")

    return "\n".join(lines)


def count_matches(path: str, needle: str) -> int:
    """Count how many times needle appears in a file.

    Useful for detecting ambiguous edits before attempting them.
    """
    try:
        content = Path(path).read_text(errors="replace")
        return content.count(needle)
    except OSError:
        return 0
