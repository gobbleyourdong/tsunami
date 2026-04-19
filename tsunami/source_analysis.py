"""Source-code analysis helpers — shared semantics for "is this a stub?"
and friends.

Layer 6 of the 'eliminate hardcoded brittle surfaces' pass. Four
duplicated `is_stub` checks across agent.py with DIFFERENT heuristics:

    Line  372: "TODO" in content or "Loading..." in content or len < 100
    Line  828: "TODO" or "not built yet" or (len < 200 and no import)
    Line 4135: "TODO" or len < 150
    Line 4208: "TODO" or "not built yet" or (len < 200 and no import)

All four answer the same question — "is this App.tsx the scaffold
default, or has the drone written real code?" — but each call site
diverged. A drone delivery that tripped one check might skate past
another, or vice versa.

This module centralizes the intent:

    is_scaffold_stub(path_or_content) → bool
    is_real_implementation(path_or_content) → bool   (inverse)
    has_placeholder_text(content) → bool             (just the text check)

The default heuristic uses BOTH size and placeholder-text signals,
matching the most thorough of the four inline versions. Callers that
want a custom cutoff pass `min_length=N`.
"""

from __future__ import annotations

from pathlib import Path


# Placeholder phrases the react-app scaffold stub (or a
# half-written drone attempt) contains. Any occurrence → stub.
_PLACEHOLDER_PHRASES: tuple[str, ...] = (
    "TODO",
    "Loading...",
    "not built yet",
    "Replace with your app content",
    "TODO:",
)


def has_placeholder_text(content: str) -> bool:
    """True if the file contents contain any scaffold-stub placeholder
    string. Case-sensitive on the exact phrases — scaffold uses these
    verbatim; drone output normally doesn't.
    """
    return any(p in content for p in _PLACEHOLDER_PHRASES)


def is_scaffold_stub(
    path_or_content: "Path | str",
    *,
    min_length: int = 200,
    require_import: bool = True,
) -> bool:
    """True if the file looks like a scaffold stub rather than real code.

    A file is a stub when ANY of these hold:
      - It contains a known placeholder phrase ("TODO", "Loading...", ...)
      - Its length is below `min_length` AND (if `require_import`) it
        doesn't `import` anything — very short files that aren't
        importing scaffold UI are almost certainly un-edited templates.

    Accepts either a Path (reads the file) or a raw string (checks
    directly). Missing files are treated as stubs (nothing to ship).
    """
    if isinstance(path_or_content, Path):
        try:
            content = path_or_content.read_text()
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            return True
    else:
        content = path_or_content
    if has_placeholder_text(content):
        return True
    if len(content) < min_length:
        if not require_import:
            return True
        low = content.lower()
        if "import" not in low:
            return True
    return False


def is_real_implementation(
    path_or_content: "Path | str",
    *,
    min_length: int = 200,
) -> bool:
    """Inverse of is_scaffold_stub — readable name for the positive case."""
    return not is_scaffold_stub(path_or_content, min_length=min_length)


__all__ = [
    "has_placeholder_text",
    "is_scaffold_stub",
    "is_real_implementation",
]
