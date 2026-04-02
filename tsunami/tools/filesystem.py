"""File system tools — read, write, edit, append.

The file system is the agent's long-term memory.
Everything important must be saved to files as it's discovered.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult


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

    return None


def _resolve_path(path: str, workspace_dir: str) -> Path:
    """Resolve a file path to an absolute path inside the workspace.

    Handles all the weird ways the 9B writes paths:
    - ./workspace/deliverables/x/file.tsx
    - workspace/deliverables/x/file.tsx
    - deliverables/x/file.tsx
    - /absolute/path/to/file.tsx
    """
    p = Path(path)

    # Already absolute — use as-is
    if p.is_absolute() or path.startswith("~"):
        return p.expanduser().resolve()

    # Strip leading ./ if present
    path_clean = path.lstrip("./") if path.startswith("./") else path

    # Strip workspace dir name prefix (e.g. "workspace/deliverables/..." → "deliverables/...")
    ws_name = Path(workspace_dir).name
    if path_clean.startswith(ws_name + "/"):
        path_clean = path_clean[len(ws_name) + 1:]

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
            p = _resolve_path(path, self.config.workspace_dir)
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
            p = _resolve_path(path, self.config.workspace_dir)
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
            p = _resolve_path(path, self.config.workspace_dir)
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

                return ToolResult(f"Text not found in {path}. Make sure old_text matches exactly (check whitespace and quotes).", is_error=True)
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
            p = _resolve_path(path, self.config.workspace_dir)
            err = _is_safe_write(p, self.config.workspace_dir)
            if err:
                return ToolResult(err, is_error=True)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a") as f:
                f.write(content)
            return ToolResult(f"Appended {len(content)} chars to {p}")
        except Exception as e:
            return ToolResult(f"Error appending to {path}: {e}", is_error=True)
