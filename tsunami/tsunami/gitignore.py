"""Gitignore-aware file filtering for search operations.


Parses .gitignore files and filters glob/grep results to exclude
ignored files. Also excludes VCS directories (.git, .svn, etc.).

Works with ripgrep's --glob negation pattern when available,
falls back to Python pathspec matching.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("tsunami.gitignore")

# VCS directories to always exclude 
VCS_DIRECTORIES = frozenset({
    ".git", ".svn", ".hg", ".bzr", ".jj", ".sl",
})

# Common directories to exclude (not in gitignore but rarely useful)
COMMON_EXCLUDES = frozenset({
    "node_modules", "__pycache__", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build",
    ".eggs", "*.egg-info",
})


def parse_gitignore(gitignore_path: str | Path) -> list[str]:
    """Parse a .gitignore file into a list of patterns.

    Returns patterns suitable for glob negation.
    """
    path = Path(gitignore_path)
    if not path.exists():
        return []

    patterns = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Skip negation patterns (complex, rarely needed for search)
            if line.startswith("!"):
                continue
            patterns.append(line)
    except OSError:
        pass

    return patterns


def find_gitignore_patterns(directory: str | Path) -> list[str]:
    """Find and parse all applicable .gitignore files.

    Walks up from directory to find .gitignore files (closest first).
    Also includes the root .gitignore if different.
    """
    patterns = []
    dir_path = Path(directory).resolve()

    # Walk up to find .gitignore files
    current = dir_path
    for _ in range(20):  # safety limit
        gi = current / ".gitignore"
        if gi.exists():
            patterns.extend(parse_gitignore(gi))
        if current.parent == current:
            break
        current = current.parent

    return patterns


def should_exclude(path: str | Path, patterns: list[str] | None = None) -> bool:
    """Check if a path should be excluded based on gitignore + VCS rules.

    Quick check without full pathspec matching — covers the common cases.
    """
    p = Path(path)

    # Always exclude VCS directories
    for part in p.parts:
        if part in VCS_DIRECTORIES:
            return True

    # Check common excludes
    for part in p.parts:
        if part in COMMON_EXCLUDES:
            return True
        # Check glob-style patterns in COMMON_EXCLUDES
        for exc in COMMON_EXCLUDES:
            if "*" in exc:
                import fnmatch
                if fnmatch.fnmatch(part, exc):
                    return True

    # Check gitignore patterns
    if patterns:
        name = p.name
        rel = str(p)
        for pattern in patterns:
            # Directory pattern (trailing /)
            if pattern.endswith("/"):
                dirname = pattern.rstrip("/")
                if dirname in p.parts:
                    return True
            # Simple name match
            elif "/" not in pattern:
                import fnmatch
                if fnmatch.fnmatch(name, pattern):
                    return True
            # Path match
            else:
                import fnmatch
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(rel, f"**/{pattern}"):
                    return True

    return False


def filter_paths(paths: list[str], base_dir: str | Path = ".") -> list[str]:
    """Filter a list of paths, excluding gitignored and VCS files.

    Loads .gitignore patterns from base_dir and applies them.
    """
    patterns = find_gitignore_patterns(base_dir)
    return [p for p in paths if not should_exclude(p, patterns)]


def ripgrep_ignore_args(directory: str | Path) -> list[str]:
    """Generate ripgrep --glob arguments for gitignore patterns.

    
    Handles the ripgrep quirk where non-absolute paths need ** prefix.
    """
    patterns = find_gitignore_patterns(directory)
    args = []

    # Always exclude VCS directories
    for vcs in VCS_DIRECTORIES:
        args.extend(["--glob", f"!{vcs}/"])

    # Gitignore patterns
    for pattern in patterns:
        if pattern.startswith("/"):
            args.extend(["--glob", f"!{pattern}"])
        else:
            # Ripgrep quirk: non-absolute patterns need **/ prefix
            args.extend(["--glob", f"!**/{pattern}"])

    return args
