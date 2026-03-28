"""File system tools — read, write, edit, append.

The file system is the agent's long-term memory.
Everything important must be saved to files as it's discovered.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult


def _resolve_path(path: str, workspace_dir: str) -> Path:
    """Resolve a file path.

    If the path is relative (doesn't start with / or ~), resolve it
    relative to the workspace directory. This ensures the agent writes
    files into the workspace, not the process CWD.

    Also strips redundant workspace prefix to avoid double-nesting
    (e.g., model writes "workspace/deliverables/x" which would become
    "workspace/workspace/deliverables/x" without this fix).
    """
    p = Path(path)
    if not p.is_absolute() and not path.startswith("~"):
        # Strip workspace dir name prefix if model included it
        ws_name = Path(workspace_dir).name  # e.g. "workspace"
        parts = p.parts
        if parts and parts[0] == ws_name:
            p = Path(*parts[1:]) if len(parts) > 1 else Path(".")
        # Also handle "./workspace/..." or "workspace/..."
        clean = str(p)
        if clean.startswith(f"./{ws_name}/"):
            p = Path(clean[len(f"./{ws_name}/"):])
        p = Path(workspace_dir) / p
    return p.expanduser().resolve()


class FileRead(BaseTool):
    name = "file_read"
    description = "Read text content from a file. The eye: take in what exists."

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

            text = p.read_text(errors="replace")
            lines = text.splitlines()
            total = len(lines)
            selected = lines[offset:offset + limit]
            numbered = [f"{i + offset + 1:>5} | {line}" for i, line in enumerate(selected)]
            header = f"[{p.name}] Lines {offset+1}-{offset+len(selected)} of {total}"
            return ToolResult(header + "\n" + "\n".join(numbered))
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
            p.parent.mkdir(parents=True, exist_ok=True)
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
            if not p.exists():
                return ToolResult(f"File not found: {path}", is_error=True)

            content = p.read_text()
            count = content.count(old_text)
            if count == 0:
                return ToolResult(f"Text not found in {path}", is_error=True)
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

    async def execute(self, path: str, content: str, **kw) -> ToolResult:
        try:
            p = _resolve_path(path, self.config.workspace_dir)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a") as f:
                f.write(content)
            return ToolResult(f"Appended {len(content)} chars to {p}")
        except Exception as e:
            return ToolResult(f"Error appending to {path}: {e}", is_error=True)
