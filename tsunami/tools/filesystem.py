"""File system tools — read, write, edit, append.

The file system is the agent's long-term memory.
Everything important must be saved to files as it's discovered.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult
from ..outbound_exfil import check_outbound_exfil

# Active project path from phase machine — set by agent.py after phase transitions.
# Used by _resolve_path to deterministically resolve bare paths like "src/App.tsx".
_active_project: str | None = None

# Deliverable directory NAMES (not full paths) that ProjectInit created in this
# Python process. Used by _is_safe_write to refuse silent overwrites of prior
# sessions' deliverables — see QA-3's REAL-TIME DESTRUCTION CONFIRMED bug.
_session_created_projects: set[str] = set()

# Name of the most recent deliverable this session (last ProjectInit). Used by
# _resolve_path as a high-priority fallback when the agent writes to a bare
# `src/...` path — beats the mtime heuristic which can pick a stale project.
# See QA-3 Test 18b MEDIUM: `file_write path="src/App.tsx"` dropped because
# active_project was None and mtime resolved to the wrong deliverable.
_session_last_project: str | None = None

# QA-1 Playtest Fire 119: deliverables can ship with Phase-N in rendered text
# because the message_result gate targeted the wrong project (mtime fallback
# picked a neighbour when _session_last_project was None — e.g. if agent
# wrote App.tsx without a preceding project_init). Track the deliverable that
# received the LAST successful file_write / file_edit / file_append as a
# second fallback — most reliable signal that "this is the project being
# actively worked on right now".
_last_written_deliverable: str | None = None

# Original task prompt for this session, captured by agent.run on entry.
# Used by message_result's gate to verify deliverable content is on-topic
# (catches QA-2's cross-task context leakage where a prior task's content
# bled into a new prompt's deliverable).
_session_task_prompt: str = ""


def set_active_project(project_path: str | None):
    """Called by agent.py when phase machine detects the active project."""
    global _active_project
    _active_project = project_path


def register_session_project(name: str):
    """Called by ProjectInit when it creates a fresh deliverable dir."""
    global _session_last_project
    _session_created_projects.add(name)
    _session_last_project = name


def _validate_structured_format(path: Path, content: str) -> str | None:
    """Parse-validate the file based on its extension. Returns None if the
    content is valid or the format is unknown/freeform; returns a short
    error string if parsing failed. Covers the common "model wrote
    a structured config file and got the syntax subtly wrong" case so the
    model sees the error immediately instead of at build/runtime.

    Skips empty content (empty is "valid" for most formats) and skips formats
    we'd hit false-positives on (e.g. JSX files ending in .tsx are not pure
    TypeScript and we don't type-check here; that's the compile gate's job).
    """
    if not content.strip():
        return None
    ext = path.suffix.lower()
    try:
        if ext == ".json":
            import json as _j
            _j.loads(content)
        elif ext in (".yaml", ".yml"):
            try:
                import yaml as _y
                _y.safe_load(content)
            except ImportError:
                return None  # pyyaml not installed; skip
        elif ext == ".toml":
            try:
                import tomllib as _t  # py3.11+
            except ImportError:
                try:
                    import tomli as _t
                except ImportError:
                    return None
            _t.loads(content) if hasattr(_t, "loads") else _t.loads(content.encode())
        elif ext == ".xml" or ext == ".svg":
            import xml.etree.ElementTree as _e
            _e.fromstring(content)
        # Skip .tsx/.ts/.js/.py/.html/.css/.md — these have their own validators
        # (compile gate, lint, etc.) and often contain intentionally-novel syntax
        # (JSX, template literals) that trip parse-validate.
    except Exception as e:
        msg = str(e).replace("\n", " ")[:200]
        return f"{ext} parse error: {msg}"
    return None


def _note_write_to_deliverable(resolved_path: Path, workspace_dir: str):
    """Record the deliverable that received a successful write. The gate
    uses this as a third fallback when _active_project + _session_last_project
    are both None (QA-1 Playtest Fire 119 root cause)."""
    global _last_written_deliverable
    try:
        deliv_root = Path(workspace_dir).resolve() / "deliverables"
        rel = resolved_path.relative_to(deliv_root)
        # Top-level component is the deliverable name.
        parts = rel.parts
        if parts and not parts[0].startswith("."):
            _last_written_deliverable = parts[0]
    except (ValueError, OSError):
        pass


def get_effective_target_project() -> str | None:
    """Return the best-guess name of the deliverable the gate should check.
    Priority: _session_last_project (most intent) → _last_written_deliverable
    (most recent write). mtime-fallback stays in the gate itself."""
    return _session_last_project or _last_written_deliverable


def _extract_post_pivot(text: str) -> str:
    """If the prompt contains a revision marker ('scratch that', 'scrap that',
    'actually no'), return only the text AFTER the last marker — that's the
    user's real intent. Otherwise return the original prompt unchanged.
    Used so the delivery gate compares against the post-pivot spec, not the
    pre-pivot spec the user already retracted (QA-3 Test 10 scratch-that HIGH).
    """
    import re as _re
    lowered = text.lower()
    # Find the latest match end among the supported markers.
    best_end = -1
    for marker in (r'\bscratch that\b', r'\bscrap that\b', r'\bactually\s*,?\s*no\b'):
        for m in _re.finditer(marker, lowered):
            if m.end() > best_end:
                best_end = m.end()
    if best_end == -1:
        return text
    # Skip trailing punctuation / connector after the marker so we land on real content.
    tail = text[best_end:]
    tail = _re.sub(r'^[\s,.;:—–\-]+(?:just\s+|instead[\s,.;:—–\-]*)?', '', tail)
    return tail if len(tail) >= 15 else text  # fall back if post-pivot is too short


def set_session_task_prompt(text: str):
    """Called by agent.run on entry to record the task prompt for delivery checks."""
    global _session_task_prompt
    _session_task_prompt = _extract_post_pivot(text)


def _is_safe_write(p: Path, workspace_dir: str) -> str | None:
    """Check if a write path is safe. Returns error message or None if OK."""
    import os
    resolved = str(p.resolve())
    ark_dir = str(Path(workspace_dir).parent.resolve())

    # Must be inside the ark project directory.
    # Use sep-suffixed prefix so /tmp/tsunami_smoke isn't seen as inside /tmp
    # when ark_dir is /tmp (string-prefix bug fix, 2026-04-13).
    if not (resolved == ark_dir or resolved.startswith(ark_dir + os.sep)):
        return f"BLOCKED: Cannot write outside project directory. Path: {resolved}"

    # Block writes to tsunami source code (the agent itself).
    tsunami_dir = str(Path(ark_dir) / "tsunami")
    if resolved == tsunami_dir or resolved.startswith(tsunami_dir + os.sep):
        return f"BLOCKED: Cannot write to tsunami source code. Use workspace/deliverables/ for output."

    # Block writes to models directory.
    models_dir = str(Path(ark_dir) / "models")
    if resolved == models_dir or resolved.startswith(models_dir + os.sep):
        return f"BLOCKED: Cannot write to models directory."

    # Config protection — prevent weakening quality gates (ECC pattern)
    protected_configs = [
        ".eslintrc", "eslint.config", "biome.json", "ruff.toml",
        ".prettierrc", "tsconfig.json", "tsconfig.app.json",
        ".gitignore", "package-lock.json", "yarn.lock",
    ]
    filename = p.name.lower()
    # Only protect configs outside of workspace/deliverables (project configs are fine)
    deliverables = str(Path(workspace_dir) / "deliverables")
    if not resolved.startswith(deliverables):
        for config in protected_configs:
            if filename == config:
                return f"BLOCKED: Cannot modify {p.name} — config protection. Fix the code, not the config."

    # Protect scaffold infrastructure files — the 9B overwrites these, breaking the project
    scaffold_files = ["main.tsx", "vite.config.ts", "index.css"]
    if resolved.startswith(str(Path(workspace_dir) / "deliverables")):
        if filename in scaffold_files and p.exists():
            return f"BLOCKED: {p.name} is scaffold infrastructure — don't overwrite it. Write your code in App.tsx and src/components/."

    # Refuse silent overwrites of prior-session deliverables. Triggered by QA-3's
    # REAL-TIME DESTRUCTION case: agent skipped project_init, picked an existing
    # similar-name deliverable, and clobbered its App.tsx with the new task's code.
    deliv_root = Path(workspace_dir) / "deliverables"
    try:
        rel = p.resolve().relative_to(deliv_root.resolve())
    except (ValueError, OSError):
        rel = None
    if rel is not None and rel.parts:
        project_name = rel.parts[0]
        if (
            project_name not in _session_created_projects
            and p.exists()
            and p.stat().st_size > 200
        ):
            return (
                f"BLOCKED: {project_name} was not created in this session — refusing to "
                f"overwrite {p.name} ({p.stat().st_size} bytes). Call project_init with a "
                f"new name to scaffold a fresh deliverable for this task."
            )

    # QA-3 Fire 79: block writes to workspace ROOT (bare files directly under
    # workspace/ with no subdir prefix). Agents should always put output inside
    # workspace/deliverables/<name>/. A bare workspace/qa3_marker.txt plant is
    # a prompt-injection vector (cross-session pollution). Existing top-level
    # directories (.observations, .memory, .history, deliverables, assets, etc.)
    # are untouched — only BARE FILE writes to the workspace root are refused.
    workspace_resolved = str(Path(workspace_dir).resolve())
    try:
        parent_resolved = str(p.parent.resolve())
    except OSError:
        parent_resolved = ""
    if parent_resolved == workspace_resolved and not p.exists():
        return (
            f"BLOCKED: {p.name} would land directly in workspace/ root. "
            f"Put files inside workspace/deliverables/<project>/ instead. "
            f"Call project_init if you need a fresh scaffold."
        )

    # QA-3 Fire 73: block writes to any path with a `node_modules/` component.
    # Dependencies are managed via npm install; direct file_write to them is
    # supply-chain poisoning. Confirmed attack on disk: agent overwrote
    # workspace/node_modules/react/cjs/react.production.min.js (6930B → 63B
    # console.log payload). Narrow path-segment check — no false-positive on
    # legitimate tooling (nothing legit writes to node_modules via our agent).
    if any(part == "node_modules" for part in p.parts):
        return (
            f"BLOCKED: refuse to write inside node_modules/ — dependencies "
            f"must be managed via `npm install`, never direct file_write. "
            f"Supply-chain poisoning vector."
        )

    return None


def _resolve_path(path: str, workspace_dir: str, active_project: str | None = None) -> Path:
    """Resolve a file path to an absolute path inside the workspace.

    Handles all the weird ways the model writes paths:
    - ./workspace/deliverables/x/file.tsx
    - workspace/deliverables/x/file.tsx
    - /workspace/deliverables/x/file.tsx  (absolute — legacy training artifact)
    - deliverables/x/file.tsx
    - src/App.tsx  (bare — resolves to active project)

    active_project: known project path from phase machine (e.g. "workspace/deliverables/calc")
    """
    import re

    # Clean hallucinated fragments: [project], [proje...], -'garbage'
    path = re.sub(r'\[project[^\]]*\]?', '', path)
    path = re.sub(r'\[[^\]]*\]', '', path)
    path = re.sub(r"\-'[^']*'?", '', path)
    # Clean trailing hyphens left after bracket removal (e.g. "calc-[project]/" → "calc-/")
    path = re.sub(r'-+/', '/', path)
    path = path.strip().rstrip("/")

    p = Path(path)

    # Absolute /workspace/ paths — legacy training artifact, rewrite to relative
    if path.startswith("/workspace/"):
        path = path[len("/workspace/"):]
        p = Path(path)
    elif p.is_absolute() or path.startswith("~"):
        return p.expanduser().resolve()

    # Strip leading ./ if present
    path_clean = path.lstrip("./") if path.startswith("./") else path

    # Strip workspace dir name prefix (e.g. "workspace/deliverables/..." → "deliverables/...")
    ws_name = Path(workspace_dir).name
    if path_clean.startswith(ws_name + "/"):
        path_clean = path_clean[len(ws_name) + 1:]
    # Also strip literal "workspace/" prefix — v14 training data and system
    # messages use this convention regardless of actual workspace_dir name
    elif path_clean.startswith("workspace/"):
        path_clean = path_clean[len("workspace/"):]

    # If path starts with src/ or components/, resolve inside the KNOWN active project
    if path_clean.startswith(("src/", "components/", "public/")):
        # Prefer phase machine's active project (deterministic) over mtime (unstable)
        if active_project:
            project_dir = Path(workspace_dir) / active_project.replace("workspace/", "", 1) \
                if active_project.startswith("workspace/") else Path(workspace_dir) / active_project
            if project_dir.exists():
                return (project_dir / path_clean).resolve()

        # Second: the most recent deliverable ProjectInit created THIS session.
        # More reliable than mtime — mtime can be bumped by concurrent QA builds
        # touching other deliverables (QA-3 Test 18b MEDIUM: relative-path write
        # landed in the wrong deliverable because mtime resolved elsewhere).
        if _session_last_project:
            project_dir = Path(workspace_dir) / "deliverables" / _session_last_project
            if project_dir.exists():
                return (project_dir / path_clean).resolve()

        # Fallback: most recent project by mtime
        deliverables = Path(workspace_dir) / "deliverables"
        if deliverables.exists():
            projects = sorted(
                [d for d in deliverables.iterdir() if d.is_dir() and (d / "package.json").exists()],
                key=lambda p: p.stat().st_mtime, reverse=True
            )
            if projects:
                return (projects[0] / path_clean).resolve()

    # Resolve relative to workspace dir
    return (Path(workspace_dir) / path_clean).resolve()


# Pre-read file size gate (.
# Files larger than this are rejected before reading — use offset/limit.
MAX_FILE_SIZE_BYTES = 256 * 1024  # 256 KB


class FileRead(BaseTool):
    name = "file_read"
    description = (
        "Read text content from a file. Files larger than 256KB require "
        "offset and limit parameters. When you already know which part of "
        "the file you need, only read that part."
    )
    concurrent_safe = True  # read-only — safe to run in parallel

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"},
                "offset": {"type": "integer", "description": "Line number to start from (0-indexed)", "default": 0},
                "limit": {"type": "integer", "description": "Max lines to read", "default": 500},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, offset: int = 0, limit: int = 500, **kw) -> ToolResult:
        try:
            p = _resolve_path(path, self.config.workspace_dir, _active_project)
            if not p.exists():
                return ToolResult(f"File not found: {path}", is_error=True)
            if not p.is_file():
                return ToolResult(f"Not a file: {path}", is_error=True)

            # Pre-read size gate (.
            # Only enforce when no explicit limit was provided (user wants whole file)
            file_size = p.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES and limit >= 500 and offset == 0:
                size_kb = file_size / 1024
                total_lines = p.read_text(errors="replace").count("\n") + 1
                return ToolResult(
                    f"File too large ({size_kb:.0f} KB, ~{total_lines} lines). "
                    f"Use offset and limit to read specific portions:\n"
                    f"  file_read(path=\"{path}\", offset=0, limit=100)  # first 100 lines\n"
                    f"  file_read(path=\"{path}\", offset=100, limit=100)  # lines 101-200\n"
                    f"Or use match_grep to search for specific content.",
                    is_error=True,
                )

            text = p.read_text(errors="replace")
            lines = text.splitlines()
            total = len(lines)
            selected = lines[offset:offset + limit]
            numbered = [f"{i + offset + 1:>5} | {line}" for i, line in enumerate(selected)]
            result = "\n".join(numbered)

            # Cap output at 8000 chars (~2000 tokens) to prevent context overflow
            max_chars = 8000
            if len(result) > max_chars:
                # Find how many lines fit in the cap
                char_count = 0
                lines_shown = 0
                for line in numbered:
                    char_count += len(line) + 1
                    if char_count > max_chars:
                        break
                    lines_shown += 1
                result = "\n".join(numbered[:lines_shown])
                next_offset = offset + lines_shown
                result += f"\n\n[TRUNCATED at line {next_offset} of {total}. Save your notes, then call file_read with offset={next_offset} to continue.]"

            header = f"[{p.name}] Lines {offset+1}-{min(offset+len(numbered), total)} of {total}"
            return ToolResult(header + "\n" + result)
        except Exception as e:
            return ToolResult(f"Error reading {path}: {e}", is_error=True)


class FileWrite(BaseTool):
    name = "file_write"
    description = "Create or overwrite a file with full content. The hand: bring something into existence."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to write to"},
                "content": {"type": "string", "description": "Full file content"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str, **kw) -> ToolResult:
        try:
            p = _resolve_path(path, self.config.workspace_dir, _active_project)
            err = _is_safe_write(p, self.config.workspace_dir)
            if err:
                return ToolResult(err, is_error=True)
            # QA-3 Fire 118: decode unicode escapes (`\uXXXX → char`) BEFORE
            # content gates fire. The decoder was previously a post-gate
            # "helpful" normalization for models double-escaping characters
            # like `÷` (U+00F7), but its placement let attackers emit
            # `"\u0068ttps://..."` to evade the `https://` literal match in
            # check_outbound_exfil — the gate approved, then the decoder
            # rewrote `\u0068` to `h` on disk. Moving the decode here makes
            # gates see what ACTUALLY lands on disk.
            import re as _u_re
            content = _u_re.sub(
                r'\\u([0-9a-fA-F]{4})',
                lambda m: chr(int(m.group(1), 16)),
                content,
            )
            # QA-3 Fire 105 / Fire 109: config-file plant with attacker URL.
            # Multiple file shapes bake external URLs into build- or runtime
            # behavior where an App.tsx content scan would miss them:
            #   .env / .env.*      — Vite VITE_* baked into production bundle
            #   .npmrc             — `npm install` pulls from attacker registry
            #   .yarnrc / .yarnrc.yml — yarn registry redirect
            #   .pnpmrc            — pnpm registry redirect
            #   .gitconfig / .git/config — git-fetch URL redirect
            # All share the same attack shape: a single http(s)://attacker URL
            # in a config value. Localhost / private-net / path-relative refs
            # pass (legit dev endpoints).
            _config_shape = (
                p.name == ".env" or p.name.startswith(".env.")
                or p.name == ".npmrc"
                or p.name in (".yarnrc", ".yarnrc.yml")
                or p.name == ".pnpmrc"
                or p.name == ".gitconfig"
                or (p.parent.name == ".git" and p.name == "config")
            )
            if _config_shape:
                import re as _cfg_re
                urls = _cfg_re.findall(r'https?://([^\s/\'"]+)', content)
                external = [u for u in urls if not _cfg_re.match(
                    r'^(localhost|127\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.|0\.0\.0\.0)',
                    u
                )]
                if external:
                    return ToolResult(
                        f"BLOCKED: {p.name} is a config-shape file and contains external URL(s) "
                        f"({', '.join(sorted(set(external))[:3])}). These files drive build-time or "
                        f"runtime behavior (VITE_* → dist bundle, .npmrc → `npm install` registry, "
                        f".yarnrc/.pnpmrc → same for yarn/pnpm, .gitconfig → git fetch URL). An "
                        f"external URL here is a supply-chain / exfiltration vector. Use localhost / "
                        f"private-net refs, or if external is genuinely needed, hardcode in the "
                        f"component (user-visible) instead of a config file.",
                        is_error=True,
                    )
            exfil_err = check_outbound_exfil(content, p.name, _session_task_prompt)
            if exfil_err:
                return ToolResult(exfil_err, is_error=True)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Fix double-escaped sequences from models
            if "\n" not in content and "\\n" in content:
                content = content.replace("\\n", "\n").replace("\\t", "\t")
            # Auto-inject CSS import into App.tsx if missing
            if p.name == "App.tsx" and "index.css" not in content and p.parent.name == "src":
                if (p.parent / "index.css").exists():
                    content = 'import "./index.css"\n' + content
            # Auto-inject React hook imports when hooks are used without import
            # The 2B forgets this constantly — useState, useEffect, useRef etc.
            if p.suffix == ".tsx" and "deliverables/" in str(p):
                import re as _hook_re
                hooks_used = set(_hook_re.findall(r'\b(useState|useEffect|useRef|useCallback|useMemo|useContext)\b', content))
                if hooks_used and 'from "react"' not in content and "from 'react'" not in content:
                    hook_list = ", ".join(sorted(hooks_used))
                    content = f'import {{ {hook_list} }} from "react"\n' + content

            # NOTE: unicode-escape decode moved above the gates (Fire 118)
            # so on-disk content matches what gates saw.
            p.write_text(content)
            _note_write_to_deliverable(p, self.config.workspace_dir)
            lines = content.count("\n") + 1

            # Parse-validate known structured formats. Covers the "model
            # outputs a file type it's rarely seen" case — if the result
            # isn't valid JSON/YAML/TOML/XML, surface the parser error so
            # the model can fix the syntax rather than shipping broken
            # config. Catches malformed JSON in package.json, invalid YAML
            # in a GitHub Action, stale TOML in a pyproject, etc.
            parse_err = _validate_structured_format(p, content)
            if parse_err:
                return ToolResult(
                    f"Wrote {lines} lines to {p}\n"
                    f"WARNING: file did not parse cleanly — {parse_err}\n"
                    f"Fix the syntax error before relying on this file.",
                    is_error=True,
                )
            return ToolResult(f"Wrote {lines} lines to {p}")
        except Exception as e:
            return ToolResult(f"Error writing {path}: {e}", is_error=True)


class FileEdit(BaseTool):
    name = "file_edit"
    description = "Make targeted modifications to an existing file. The scalpel: precise changes without destroying context."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "old_text": {"type": "string", "description": "Exact text to find and replace"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(self, path: str, old_text: str, new_text: str, **kw) -> ToolResult:
        try:
            p = _resolve_path(path, self.config.workspace_dir, _active_project)
            err = _is_safe_write(p, self.config.workspace_dir)
            if err:
                return ToolResult(err, is_error=True)
            if not p.exists():
                return ToolResult(f"File not found: {path}", is_error=True)

            content = p.read_text()
            count = content.count(old_text)
            if count == 0:
                # Fuzzy match: try stripping trailing whitespace from both
                stripped_content = "\n".join(l.rstrip() for l in content.split("\n"))
                stripped_old = "\n".join(l.rstrip() for l in old_text.split("\n"))
                if stripped_content.count(stripped_old) == 1:
                    # Found with whitespace normalization — do the replace on stripped
                    new_content = stripped_content.replace(stripped_old, new_text, 1)
                    exfil_err = check_outbound_exfil(new_content, p.name, _session_task_prompt)
                    if exfil_err:
                        return ToolResult(exfil_err, is_error=True)
                    p.write_text(new_content)
                    _note_write_to_deliverable(p, self.config.workspace_dir)
                    return ToolResult(f"Edited {p}: replaced 1 occurrence (whitespace-normalized match)")

                # Try with curly quote normalization
                def normalize_quotes(s):
                    return s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
                norm_content = normalize_quotes(content)
                norm_old = normalize_quotes(old_text)
                if norm_content.count(norm_old) == 1:
                    idx = norm_content.index(norm_old)
                    actual = content[idx:idx+len(old_text)]
                    new_content = content.replace(actual, new_text, 1)
                    exfil_err = check_outbound_exfil(new_content, p.name, _session_task_prompt)
                    if exfil_err:
                        return ToolResult(exfil_err, is_error=True)
                    p.write_text(new_content)
                    _note_write_to_deliverable(p, self.config.workspace_dir)
                    return ToolResult(f"Edited {p}: replaced 1 occurrence (quote-normalized match)")

                # Indent-normalized fuzzy match — QA-3 Test 32: agent emits old_text
                # at column 0 but on-disk has consistent leading indent (e.g. 10-space
                # JSX indentation). Without this, the placeholder-fix recovery loop
                # silently fails and the agent's retry goes nowhere. Match line-by-line
                # on lstripped text; re-indent new_text with the same prefix we found.
                old_lines = old_text.split("\n")
                content_lines = content.split("\n")
                old_stripped = [l.lstrip() for l in old_lines]
                n = len(old_lines)
                indent_matches: list[tuple[int, str]] = []
                for i in range(0, len(content_lines) - n + 1):
                    window = content_lines[i:i+n]
                    indent: str | None = None
                    ok = True
                    for cl, ol_stripped in zip(window, old_stripped):
                        # Empty old-line matches any (possibly indented) blank line
                        if not ol_stripped:
                            if cl.strip():
                                ok = False
                                break
                            continue
                        if cl.lstrip() != ol_stripped:
                            ok = False
                            break
                        cur = cl[:len(cl) - len(cl.lstrip())]
                        if indent is None:
                            indent = cur
                        elif cur != indent:
                            ok = False
                            break
                    if ok and indent is not None:
                        indent_matches.append((i, indent))
                if len(indent_matches) == 1:
                    start, indent = indent_matches[0]
                    new_lines = new_text.split("\n")
                    reindented = [indent + nl if nl else nl for nl in new_lines]
                    replaced = content_lines[:start] + reindented + content_lines[start+n:]
                    new_content = "\n".join(replaced)
                    exfil_err = check_outbound_exfil(new_content, p.name, _session_task_prompt)
                    if exfil_err:
                        return ToolResult(exfil_err, is_error=True)
                    p.write_text(new_content)
                    _note_write_to_deliverable(p, self.config.workspace_dir)
                    return ToolResult(
                        f"Edited {p}: replaced 1 occurrence (indent-normalized match, "
                        f"{len(indent)} leading chars restored)"
                    )

                # Show the model what's actually in the file so it can fix the find string
                preview_lines = content.splitlines()[:30]
                preview = "\n".join(f"  {i+1}: {l}" for i, l in enumerate(preview_lines))
                return ToolResult(
                    f"Text not found in {path}. Your find string doesn't match.\n"
                    f"TIP: Use file_write to rewrite the entire file instead of file_edit.\n"
                    f"Current file (first 30 lines):\n{preview}",
                    is_error=True
                )
            if count > 1:
                return ToolResult(
                    f"Ambiguous: '{old_text[:60]}...' found {count} times. Provide more context.",
                    is_error=True,
                )

            new_content = content.replace(old_text, new_text, 1)
            exfil_err = check_outbound_exfil(new_content, p.name, _session_task_prompt)
            if exfil_err:
                return ToolResult(exfil_err, is_error=True)
            p.write_text(new_content)
            _note_write_to_deliverable(p, self.config.workspace_dir)
            return ToolResult(f"Edited {p}: replaced 1 occurrence")
        except Exception as e:
            return ToolResult(f"Error editing {path}: {e}", is_error=True)


class FileAppend(BaseTool):
    name = "file_append"
    description = "Add content to the end of an existing file. The accumulator: build incrementally."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to append"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str = "", content: str = "", **kw) -> ToolResult:
        try:
            p = _resolve_path(path, self.config.workspace_dir, _active_project)
            err = _is_safe_write(p, self.config.workspace_dir)
            if err:
                return ToolResult(err, is_error=True)
            existing = p.read_text() if p.exists() else ""
            exfil_err = check_outbound_exfil(existing + content, p.name, _session_task_prompt)
            if exfil_err:
                return ToolResult(exfil_err, is_error=True)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a") as f:
                f.write(content)
            _note_write_to_deliverable(p, self.config.workspace_dir)
            return ToolResult(f"Appended {len(content)} chars to {p}")
        except Exception as e:
            return ToolResult(f"Error appending to {path}: {e}", is_error=True)
