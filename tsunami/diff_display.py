"""Structured diff parsing and display.

Ported from Claude Code's gitDiff.ts patterns.
Parses unified diff output into structured hunks for better
display and analysis. Works with both git diff and inline edits.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

log = logging.getLogger("tsunami.diff_display")

# Max lines per file to include in display (from Claude Code)
MAX_LINES_PER_FILE = 400


@dataclass
class DiffHunk:
    """A single diff hunk (contiguous change block)."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = field(default_factory=list)


@dataclass
class FileDiff:
    """Diff for a single file."""
    path: str
    old_path: str | None = None  # for renames
    hunks: list[DiffHunk] = field(default_factory=list)
    is_binary: bool = False
    is_new: bool = False
    is_deleted: bool = False

    @property
    def additions(self) -> int:
        return sum(
            1 for h in self.hunks for l in h.lines if l.startswith("+")
        )

    @property
    def deletions(self) -> int:
        return sum(
            1 for h in self.hunks for l in h.lines if l.startswith("-")
        )

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions


@dataclass
class DiffResult:
    """Complete diff result with stats."""
    files: list[FileDiff] = field(default_factory=list)

    @property
    def total_additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def files_changed(self) -> int:
        return len(self.files)

    def format_stats(self) -> str:
        """One-line summary like git's --stat."""
        parts = []
        parts.append(f"{self.files_changed} file{'s' if self.files_changed != 1 else ''} changed")
        if self.total_additions:
            parts.append(f"{self.total_additions} insertion{'s' if self.total_additions != 1 else ''}(+)")
        if self.total_deletions:
            parts.append(f"{self.total_deletions} deletion{'s' if self.total_deletions != 1 else ''}(-)")
        return ", ".join(parts)

    def format_full(self, max_lines: int = MAX_LINES_PER_FILE) -> str:
        """Full diff display with file headers and hunks."""
        parts = [self.format_stats(), ""]
        for f in self.files:
            header = f"--- {f.old_path or f.path}"
            header += f"\n+++ {f.path}"
            if f.is_new:
                header += " (new file)"
            elif f.is_deleted:
                header += " (deleted)"
            elif f.is_binary:
                header += " (binary)"
            parts.append(header)

            lines_shown = 0
            for hunk in f.hunks:
                parts.append(f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@")
                for line in hunk.lines:
                    if lines_shown >= max_lines:
                        parts.append(f"... [{len(hunk.lines) - lines_shown} more lines]")
                        break
                    parts.append(line)
                    lines_shown += 1
            parts.append("")

        return "\n".join(parts)


# --- Hunk header regex ---
_HUNK_RE = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
_FILE_RE = re.compile(r'^diff --git a/(.+) b/(.+)')
_NEW_FILE_RE = re.compile(r'^new file mode')
_DELETED_RE = re.compile(r'^deleted file mode')
_BINARY_RE = re.compile(r'^Binary files')
_RENAME_FROM_RE = re.compile(r'^rename from (.+)')
_RENAME_TO_RE = re.compile(r'^rename to (.+)')


def parse_unified_diff(diff_text: str) -> DiffResult:
    """Parse unified diff output into structured DiffResult.

    Handles git diff, diff -u, and similar formats.
    """
    result = DiffResult()
    current_file: FileDiff | None = None
    current_hunk: DiffHunk | None = None

    for line in diff_text.split("\n"):
        # New file header
        file_match = _FILE_RE.match(line)
        if file_match:
            current_file = FileDiff(
                path=file_match.group(2),
                old_path=file_match.group(1) if file_match.group(1) != file_match.group(2) else None,
            )
            result.files.append(current_file)
            current_hunk = None
            continue

        if current_file is None:
            continue

        # File metadata
        if _NEW_FILE_RE.match(line):
            current_file.is_new = True
            continue
        if _DELETED_RE.match(line):
            current_file.is_deleted = True
            continue
        if _BINARY_RE.match(line):
            current_file.is_binary = True
            continue

        rename_from = _RENAME_FROM_RE.match(line)
        if rename_from:
            current_file.old_path = rename_from.group(1)
            continue
        rename_to = _RENAME_TO_RE.match(line)
        if rename_to:
            current_file.path = rename_to.group(1)
            continue

        # Hunk header
        hunk_match = _HUNK_RE.match(line)
        if hunk_match:
            current_hunk = DiffHunk(
                old_start=int(hunk_match.group(1)),
                old_count=int(hunk_match.group(2) or 1),
                new_start=int(hunk_match.group(3)),
                new_count=int(hunk_match.group(4) or 1),
            )
            current_file.hunks.append(current_hunk)
            continue

        # Hunk content lines
        if current_hunk is not None and (
            line.startswith("+") or line.startswith("-") or line.startswith(" ")
        ):
            current_hunk.lines.append(line)

    return result


def format_inline_edit(path: str, old_text: str, new_text: str) -> str:
    """Format an inline edit as a mini-diff for display."""
    old_lines = old_text.split("\n")
    new_lines = new_text.split("\n")

    parts = [f"--- {path}", f"+++ {path}"]
    # Simple line-by-line diff (not full Myers)
    for line in old_lines:
        if line not in new_lines:
            parts.append(f"-{line}")
    for line in new_lines:
        if line not in old_lines:
            parts.append(f"+{line}")

    if len(parts) == 2:
        return f"No visible changes in {path}"

    return "\n".join(parts)
