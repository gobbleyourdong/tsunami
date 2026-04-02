"""File matching tools — glob and grep.

The compass and the metal detector.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult

DEFAULT_IGNORED_RELATIVE_DIRS = (
    ".git",
    ".venv",
    "llama.cpp",
    "cli/node_modules",
    "workspace/.history",
    "workspace/.observations",
    "workspace/.tool_results",
    "__pycache__",
)
DEFAULT_IGNORED_BASENAMES = {
    "node_modules",
    "dist",
    ".vite",
    "__pycache__",
}


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def _ignored_prefixes(root: Path, workspace_dir: str) -> list[Path]:
    """Build ignored absolute prefixes unless the search explicitly targets one."""
    ark_dir = Path(workspace_dir).parent.resolve()
    prefixes: list[Path] = []

    for rel in DEFAULT_IGNORED_RELATIVE_DIRS:
        prefix = (ark_dir / rel).resolve()
        if _is_relative_to(root, prefix):
            # Explicit search inside an ignored tree should still work.
            continue
        if _is_relative_to(prefix, root):
            prefixes.append(prefix)

    return prefixes


def _resolve_root(directory: str, workspace_dir: str) -> Path:
    candidate = Path(directory).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    ark_dir = Path(workspace_dir).parent.resolve()
    return (ark_dir / candidate).resolve()


def _allowed_path(candidate: Path, ignored_prefixes: list[Path]) -> bool:
    return not any(_is_relative_to(candidate, prefix) for prefix in ignored_prefixes)


def _pattern_explicitly_targets_runtime_tree(pattern: str) -> bool:
    markers = ("node_modules", "dist", ".vite", "__pycache__")
    normalized = pattern.replace("\\", "/")
    return any(marker in normalized for marker in markers)


def _expand_brace_patterns(pattern: str) -> list[str]:
    """Expand simple glob brace groups like **/*.{ts,tsx} into multiple patterns."""
    match = re.search(r"\{([^{}]+)\}", pattern)
    if not match:
        return [pattern]

    options = [option.strip() for option in match.group(1).split(",") if option.strip()]
    if not options:
        return [pattern]

    prefix = pattern[:match.start()]
    suffix = pattern[match.end():]
    expanded: list[str] = []
    for option in options:
        expanded.extend(_expand_brace_patterns(f"{prefix}{option}{suffix}"))
    return expanded


def _runtime_ignore_globs(pattern: str) -> list[str]:
    if _pattern_explicitly_targets_runtime_tree(pattern):
        return []
    return [f"!**/{name}/**" for name in DEFAULT_IGNORED_BASENAMES]


def _allow_basename(candidate: Path, root: Path, pattern: str) -> bool:
    if _pattern_explicitly_targets_runtime_tree(pattern):
        return True

    try:
        rel = candidate.relative_to(root)
    except ValueError:
        rel = candidate

    return not any(part in DEFAULT_IGNORED_BASENAMES for part in rel.parts)


class MatchGlob(BaseTool):
    name = "match_glob"
    description = "Find files by name and path patterns. The compass: locate what you need."
    concurrent_safe = True

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py', 'src/**/*.ts')"},
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "limit": {"type": "integer", "description": "Max results", "default": 50},
            },
            "required": ["pattern"],
        }

    async def execute(self, pattern: str, directory: str = ".", limit: int = 50, **kw) -> ToolResult:
        try:
            root = _resolve_root(directory, self.config.workspace_dir)
            if not root.exists():
                return ToolResult(f"Directory not found: {directory}", is_error=True)

            ignored_prefixes = _ignored_prefixes(root, self.config.workspace_dir)
            matches_map: dict[Path, None] = {}
            for expanded_pattern in _expand_brace_patterns(pattern):
                for p in root.glob(expanded_pattern):
                    if (
                        p.is_file()
                        and _allowed_path(p, ignored_prefixes)
                        and _allow_basename(p, root, expanded_pattern)
                    ):
                        matches_map[p] = None
            matches = sorted(matches_map.keys(), key=lambda p: p.stat().st_mtime, reverse=True)
            results = [str(m.relative_to(root)) for m in matches[:limit]]
            total = len(matches)

            if not results:
                return ToolResult(f"No files match '{pattern}' in {root}")

            header = f"Found {total} files matching '{pattern}'"
            if total > limit:
                header += f" (showing first {limit})"

            if total > 20:
                header += f"\n⚡ {total} files found. Use python_exec to batch-read them or swell to process in parallel."

            return ToolResult(header + "\n" + "\n".join(results))
        except Exception as e:
            return ToolResult(f"Error globbing: {e}", is_error=True)


class MatchGrep(BaseTool):
    name = "match_grep"
    description = "Search file contents by regex pattern. The metal detector: find signal buried in noise."
    concurrent_safe = True

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "file_pattern": {"type": "string", "description": "Glob filter for files (e.g. '*.py')", "default": ""},
                "limit": {"type": "integer", "description": "Max results", "default": 30},
            },
            "required": ["pattern"],
        }

    async def execute(self, pattern: str, directory: str = ".", file_pattern: str = "",
                      limit: int = 30, **kw) -> ToolResult:
        try:
            root = _resolve_root(directory, self.config.workspace_dir)
            if not root.exists():
                return ToolResult(f"Directory not found: {directory}", is_error=True)

            ignored_prefixes = _ignored_prefixes(root, self.config.workspace_dir)

            if shutil.which("rg"):
                cmd = ["rg", "-n", "-e", pattern]
                if file_pattern:
                    for expanded_pattern in _expand_brace_patterns(file_pattern):
                        cmd.extend(["-g", expanded_pattern])
                for ignore_glob in _runtime_ignore_globs(file_pattern or "**/*"):
                    cmd.extend(["-g", ignore_glob])
                for prefix in ignored_prefixes:
                    rel = prefix.relative_to(root).as_posix()
                    cmd.extend(["-g", f"!{rel}/**"])
                cmd.append(".")
                result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=30)
                lines = result.stdout.strip().splitlines()
            else:
                regex = re.compile(pattern)
                matched: list[str] = []
                candidate_pattern = file_pattern or "**/*"
                seen: set[Path] = set()
                for expanded_pattern in _expand_brace_patterns(candidate_pattern):
                    for path in root.glob(expanded_pattern):
                        if (
                            not path.is_file()
                            or path in seen
                            or not _allowed_path(path, ignored_prefixes)
                            or not _allow_basename(path, root, expanded_pattern)
                        ):
                            continue
                        seen.add(path)
                        try:
                            with open(path, encoding="utf-8", errors="replace") as f:
                                for line_no, line in enumerate(f, start=1):
                                    if regex.search(line):
                                        matched.append(f"{path.relative_to(root)}:{line_no}:{line.rstrip()}")
                                        if len(matched) >= limit:
                                            break
                            if len(matched) >= limit:
                                break
                        except OSError:
                            continue
                    if len(matched) >= limit:
                        break
                lines = matched

            if not lines:
                return ToolResult(f"No matches for '{pattern}' in {root}")

            total = len(lines)
            selected = lines[:limit]
            header = f"Found {total} matches for '{pattern}'"
            if total > limit:
                header += f" (showing first {limit})"
            return ToolResult(header + "\n" + "\n".join(selected))
        except subprocess.TimeoutExpired:
            return ToolResult("Grep timed out after 30s", is_error=True)
        except Exception as e:
            return ToolResult(f"Error grepping: {e}", is_error=True)
