"""Message tools — how the agent speaks to humans.

Default to info. Use ask only when genuinely blocked.
Use result only when truly done. Every unnecessary ask
wastes the user's time.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from .base import BaseTool, ToolResult


# Exact placeholder text written by ProjectInit when scaffolding.
# If App.tsx matches this verbatim, the agent never replaced it.
_SCAFFOLD_PLACEHOLDER_APP_TSX = (
    '// TODO: Replace with your app\n'
    'export default function App() {\n'
    '  return <div>Loading...</div>\n'
    '}\n'
)

# Marker phrases that indicate the agent wrote a roadmap/stub instead of real code.
# Carefully chosen to avoid false positives on legitimate strings — e.g. `placeholder`
# would match `<input placeholder="...">` attributes, so we don't include it.
_PLACEHOLDER_PHRASES = (
    "todo: replace",
    "phase 1",
    "ready for phase",
    "will go here",
    "goes here",
    "coming soon",
)


def _check_deliverable_complete(workspace_dir: str) -> str | None:
    """Return error message if the latest deliverable looks like a placeholder.
    Returns None if deliverable is OK to ship (or if there's no React deliverable to check).
    """
    deliv_root = Path(workspace_dir) / "deliverables"
    if not deliv_root.is_dir():
        return None
    # Pick the deliverable touched most recently — that's the current task's output.
    candidates = [d for d in deliv_root.iterdir() if d.is_dir() and (d / "package.json").exists()]
    if not candidates:
        return None
    target = max(candidates, key=lambda d: d.stat().st_mtime)
    app = target / "src" / "App.tsx"
    if not app.exists():
        return None  # api-only / non-react scaffold
    try:
        content = app.read_text()
    except OSError:
        return None
    if content == _SCAFFOLD_PLACEHOLDER_APP_TSX:
        return (
            f"REFUSED: {target.name}/src/App.tsx is the unchanged scaffold placeholder. "
            f"Write the actual app code with file_write before delivering."
        )
    lower = content.lower()
    for phrase in _PLACEHOLDER_PHRASES:
        if phrase in lower:
            return (
                f"REFUSED: {target.name}/src/App.tsx still contains placeholder text "
                f"({phrase!r}). Replace it with the real implementation before delivering."
            )
    if len(content) < 300:
        return (
            f"REFUSED: {target.name}/src/App.tsx is only {len(content)} bytes — "
            f"too short to be a complete app. Write the full implementation before delivering."
        )
    return None


# Global callback for user input — set by the CLI runner
_input_callback = None
_last_displayed = None  # Track last displayed text to suppress duplicates


def set_input_callback(fn):
    global _input_callback
    _input_callback = fn


class MessageInfo(BaseTool):
    name = "message_info"
    description = "Acknowledge, update, or inform the user. No response needed. The heartbeat pulse."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Information to share with the user"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str = "", **kw) -> ToolResult:
        global _last_displayed
        if text:
            # Strip emojis — Windows console (cp1252) crashes on them
            clean = text.encode("ascii", errors="ignore").decode("ascii")
            print(f"\n  {clean}")
        _last_displayed = text
        return ToolResult("Message delivered.")


class MessageAsk(BaseTool):
    name = "message_ask"
    description = "Request input from the user. Only use when genuinely blocked. The pause."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Question to ask the user"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str, **kw) -> ToolResult:
        print(f"\n  \033[33m?\033[0m {text}")
        if _input_callback:
            response = await _input_callback(text)
        else:
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: input("\n> "))
            except EOFError:
                # Non-interactive mode — don't block, tell model to figure it out
                return ToolResult(
                    "No user available. You are running autonomously. "
                    "Do NOT ask for help. Use file_read to examine your code, "
                    "file_edit to fix errors, and shell_exec to verify. "
                    "Make your best judgment and continue building."
                )
        return ToolResult(f"User response: {response}")


class MessageChat(BaseTool):
    name = "message_chat"
    description = (
        "Talk to the user. Keep it SHORT — one sentence max. "
        "done=true ends the task (conversation). done=false continues (status update). "
        "Use for: greetings, questions, progress updates, snag reports. Not walls of text."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Message to the user"},
                "done": {"type": "boolean", "description": "true = end the task (conversation), false = keep working (status update)", "default": True},
            },
            "required": ["text"],
        }

    async def execute(self, text: str = "", done: bool = True, **kw) -> ToolResult:
        global _last_displayed
        if text:
            clean = text.encode("ascii", errors="ignore").decode("ascii")
            prefix = "\033[36m>\033[0m" if not done else ""
            print(f"\n  {prefix} {clean}" if prefix else f"\n  {clean}")
        _last_displayed = text
        # The agent loop checks the done flag to decide whether to terminate
        return ToolResult(text, is_error=False)


class MessageResult(BaseTool):
    name = "message_result"
    description = "Deliver final outcome and end the task. The exhale: the work is done."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Final result to deliver"},
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths to attach as deliverables",
                    "default": [],
                },
            },
            "required": [],
        }

    async def execute(self, text: str = "", attachments: list[str] | None = None, **kw) -> ToolResult:
        global _last_displayed
        # Gate: don't let the agent ship an unchanged scaffold or obvious placeholder.
        # Returning is_error=True keeps the agent loop alive so it can fix and retry.
        gate_error = _check_deliverable_complete(self.config.workspace_dir)
        if gate_error:
            return ToolResult(gate_error, is_error=True)
        # Don't re-display if message_info already showed this exact text
        if text != _last_displayed:
            clean = text.encode("ascii", errors="ignore").decode("ascii")
            print(f"\n  {clean}")
        if attachments:
            print(f"  \033[2m{', '.join(attachments)}\033[0m")
        _last_displayed = None
        return ToolResult(text)
