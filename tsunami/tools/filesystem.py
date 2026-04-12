"""File system tools — read, write, edit, append.

The file system is the agent's long-term memory.
Everything important must be saved to files as it's discovered.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult

# Active project path from phase machine — set by agent.py after phase transitions.
# Used by _resolve_path to deterministically resolve bare paths like "src/App.tsx".
_active_project: str | None = None

# Deliverable directory NAMES (not full paths) that ProjectInit created in this
# Python process. Used by _is_safe_write to refuse silent overwrites of prior
# sessions' deliverables — see QA-3's REAL-TIME DESTRUCTION CONFIRMED bug.
_session_created_projects: set[str] = set()

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
    _session_created_projects.add(name)


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
    resolved = str(p.resolve())
    ark_dir = str(Path(workspace_dir).parent.resolve())

    # Must be inside the ark project directory
    if not resolved.startswith(ark_dir):
        return f"BLOCKED: Cannot write outside project directory. Path: {resolved}"

    # Block writes to tsunami source code (the agent itself)
    tsunami_dir = str(Path(ark_dir) / "tsunami")
    if resolved.startswith(tsunami_dir):
        return f"BLOCKED: Cannot write to tsunami source code. Use workspace/deliverables/ for output."

    # Block writes to models directory
    models_dir = str(Path(ark_dir) / "models")
    if resolved.startswith(models_dir):
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

    return None


def _resolve_path(path: str, workspace_dir: str, active_project: str | None = None) -> Path:
    """Resolve a file path to an absolute path inside the workspace.

    Handles all the weird ways the model writes paths:
    - ./workspace/deliverables/x/file.tsx
    - workspace/deliverables/x/file.tsx
    - /workspace/deliverables/x/file.tsx  (absolute — Docker training artifact)
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

    # Absolute /workspace/ paths — Docker training artifact, rewrite to relative
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

            # Fix unicode escapes (\\u00f7 → ÷) — models double-escape these
            if "\\u00" in content or "\\u2" in content:
                import re
                content = re.sub(
                    r'\\u([0-9a-fA-F]{4})',
                    lambda m: chr(int(m.group(1), 16)),
                    content,
                )
            p.write_text(content)
            lines = content.count("\n") + 1
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
                    p.write_text(new_content)
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
                    p.write_text(new_content)
                    return ToolResult(f"Edited {p}: replaced 1 occurrence (quote-normalized match)")

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
            p.write_text(new_content)
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
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a") as f:
                f.write(content)
            return ToolResult(f"Appended {len(content)} chars to {p}")
        except Exception as e:
            return ToolResult(f"Error appending to {path}: {e}", is_error=True)
