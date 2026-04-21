"""Discovery tools — match_glob, match_grep, summarize_file.

Audit D22 fix: the fine-tune's native_toolcall_formatter declares these
as core tools that every fine-tuned example sees. The registry had
marked them "deprecated, removed from codebase" — so every fine-tune
session emitted a tool call the registry couldn't route, producing
"unknown tool" errors and driving the model to fall back to
`shell_exec "find"/"rg"` for capabilities that should be native.

Schemas reproduced verbatim from the fine-tune's tool-declaration set
(top-level `TOOL_SCHEMAS`). Same field names the model was trained to
emit; execute() accepts both directory+pattern (training) and any
qwen-style path aliases for resilience.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult
from .filesystem import (
    _resolve_path, MAX_FILE_SIZE_BYTES, _active_project,
    _scaffold_first_block, is_scaffold_first_inlined,
)


_MAX_RESULTS_DEFAULT = 100


class MatchGlob(BaseTool):
    name = "match_glob"
    description = "Find files by name and path patterns."
    concurrent_safe = True

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern"},
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "limit": {"type": "integer", "description": "Max results", "default": _MAX_RESULTS_DEFAULT},
            },
            "required": ["pattern"],
        }

    async def execute(self, pattern: str, directory: str = ".",
                      limit: int = _MAX_RESULTS_DEFAULT, **kw) -> ToolResult:
        try:
            base = _resolve_path(directory, self.config.workspace_dir, _active_project)
            if not base.exists():
                return ToolResult(f"Directory not found: {directory}", is_error=True)
            if not base.is_dir():
                return ToolResult(f"Not a directory: {directory}", is_error=True)
            # Recursive glob if pattern contains ** or starts with **; otherwise use
            # one-level glob. Path.rglob supports recursive traversal.
            if "**" in pattern:
                matches = list(base.glob(pattern))
            else:
                matches = list(base.rglob(pattern))
            # Filter to files only (common case); caller can glob "*/" for dirs.
            files = [m for m in matches if m.is_file()]
            files.sort()
            shown = files[: max(1, int(limit))]
            if not shown:
                return ToolResult(f"No matches for pattern '{pattern}' in {base}")
            lines = [str(p.relative_to(base) if p.is_relative_to(base) else p) for p in shown]
            header = f"[match_glob] {len(shown)}"
            if len(files) > len(shown):
                header += f" of {len(files)} (limit hit)"
            header += f" matches for '{pattern}':"
            return ToolResult(header + "\n" + "\n".join(lines))
        except Exception as e:
            return ToolResult(f"match_glob error: {e}", is_error=True)


class MatchGrep(BaseTool):
    name = "match_grep"
    description = "Search file contents by regex pattern."
    concurrent_safe = True

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "file_pattern": {"type": "string", "description": "Glob filter for files", "default": "*"},
                "limit": {"type": "integer", "description": "Max results", "default": _MAX_RESULTS_DEFAULT},
            },
            "required": ["pattern"],
        }

    async def execute(self, pattern: str, directory: str = ".",
                      file_pattern: str = "*",
                      limit: int = _MAX_RESULTS_DEFAULT, **kw) -> ToolResult:
        try:
            base = _resolve_path(directory, self.config.workspace_dir, _active_project)
            if not base.exists():
                return ToolResult(f"Directory not found: {directory}", is_error=True)

            def _drop_inlined(hit_line: str) -> bool:
                """True iff the hit line targets a scaffold-first inlined
                file (pain_scaffold_first_match_grep_leak, sev 4). Current
                2026-04-20 demonstrated pattern='.*' + file_pattern='data/
                *.json' leaks every line of every inlined data file. Drop
                hits rather than fail the whole call — other files in the
                match set are still legitimate."""
                try:
                    rel = hit_line.split(":", 1)[0]
                    # hit lines are `<relpath>:<lineno>:<content>`
                    hp = (base / rel).resolve()
                    return is_scaffold_first_inlined(hp)
                except Exception:
                    return False

            # Prefer ripgrep if installed — 10-100× faster than Python. Fall
            # back to a pure-Python scan if rg isn't available.
            rg = _which("rg")
            if rg:
                cmd = [rg, "--no-heading", "--line-number", "--max-count", str(max(1, int(limit))),
                       "--glob", file_pattern, pattern, str(base)]
                try:
                    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    text = (out.stdout or "").strip()
                    if out.returncode not in (0, 1):  # 1 = no matches in rg
                        return ToolResult(f"match_grep(rg) failed: {out.stderr[:200]}", is_error=True)
                    if not text:
                        return ToolResult(f"No matches for /{pattern}/ in {base}")
                    lines = [ln for ln in text.split("\n") if not _drop_inlined(ln)]
                    if not lines:
                        return ToolResult(f"No matches for /{pattern}/ in {base}")
                    header = f"[match_grep] {len(lines)} matches for /{pattern}/:"
                    return ToolResult(header + "\n" + "\n".join(lines[: int(limit)]))
                except subprocess.TimeoutExpired:
                    return ToolResult("match_grep: rg timed out (30s)", is_error=True)
            # Fallback: Python scan
            try:
                prog = re.compile(pattern)
            except re.error as e:
                return ToolResult(f"match_grep: invalid regex: {e}", is_error=True)
            hits = []
            for path in base.rglob(file_pattern):
                if not path.is_file() or path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    continue
                # Skip scaffold-first inlined files entirely — don't even
                # open them (avoid sidechannel if is_scaffold_first_inlined
                # itself is slow per-call).
                if is_scaffold_first_inlined(path):
                    continue
                try:
                    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                        if prog.search(line):
                            hits.append(f"{path.relative_to(base)}:{n}:{line[:200]}")
                            if len(hits) >= int(limit):
                                break
                except Exception:
                    continue
                if len(hits) >= int(limit):
                    break
            if not hits:
                return ToolResult(f"No matches for /{pattern}/ in {base}")
            return ToolResult(f"[match_grep] {len(hits)} matches:\n" + "\n".join(hits))
        except Exception as e:
            return ToolResult(f"match_grep error: {e}", is_error=True)


class SummarizeFile(BaseTool):
    name = "summarize_file"
    description = "Summarize a file — show head, tail, and size."
    concurrent_safe = True

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "focus": {"type": "string", "description": "What to focus on (hint only)"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, focus: str = "", **kw) -> ToolResult:
        # Training schema calls out "fast model" summarization but this would
        # require dispatching a secondary model call. For now, deterministic
        # structural summary: first 30 + last 20 lines + size stats. Gives
        # the agent enough signal to decide whether to file_read the full
        # contents. Focus hint is recorded but not yet used to steer the
        # summary (would need a summarizer model in the loop).
        try:
            p = _resolve_path(path, self.config.workspace_dir, _active_project)
            if not p.exists():
                return ToolResult(f"File not found: {path}", is_error=True)
            if not p.is_file():
                return ToolResult(f"Not a file: {path}", is_error=True)
            # Scaffold-first inlined file: summarize_file's head+tail
            # preview equals the full file for typical data/*.json
            # (< 50 lines). Current 2026-04-20 confirmed this as a
            # 100% bypass of the file_read gate
            # (pain_scaffold_first_summarize_leak, sev 5).
            block_reason = _scaffold_first_block(
                p, tool="summarize_file", op="summarize"
            )
            if block_reason:
                return ToolResult(block_reason, is_error=True)
            size = p.stat().st_size
            text = p.read_text(errors="replace")
            lines = text.splitlines()
            total = len(lines)
            head_n = 30
            tail_n = 20
            parts = [f"[summarize_file] {path} — {total} lines, {size} bytes"]
            if focus:
                parts.append(f"focus: {focus}")
            if total <= head_n + tail_n:
                parts.append("---")
                parts.extend(f"{i+1:>5} | {ln}" for i, ln in enumerate(lines))
            else:
                parts.append(f"--- head ({head_n} lines) ---")
                parts.extend(f"{i+1:>5} | {ln}" for i, ln in enumerate(lines[:head_n]))
                parts.append(f"--- ... {total - head_n - tail_n} lines elided ... ---")
                parts.append(f"--- tail ({tail_n} lines) ---")
                start = total - tail_n
                parts.extend(f"{start+i+1:>5} | {ln}" for i, ln in enumerate(lines[-tail_n:]))
            return ToolResult("\n".join(parts))
        except Exception as e:
            return ToolResult(f"summarize_file error: {e}", is_error=True)


def _which(prog: str) -> str | None:
    for pdir in (os.environ.get("PATH") or "").split(":"):
        if not pdir:
            continue
        cand = Path(pdir) / prog
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None
