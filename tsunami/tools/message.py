"""Message tools — how the agent speaks to humans.

Default to info. Use ask only when genuinely blocked.
Use result only when truly done. Every unnecessary ask
wastes the user's time.
"""

from __future__ import annotations

import asyncio
import re
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

# Stop-words excluded from prompt/deliverable keyword overlap. Chosen narrowly to
# leave domain-specific nouns (chart, dashboard, regex, etc.) intact.
_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
    'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
    'we', 'they', 'me', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
    'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
    'about', 'into', 'through', 'before', 'after', 'above', 'below',
    'as', 'so', 'if', 'when', 'where', 'how', 'what', 'who', 'which',
    'build', 'make', 'create', 'add', 'use', 'using', 'app', 'page',
    'instead', 'actually', 'scratch', 'wait', 'just', 'now', 'then',
    'also', 'one', 'two', 'three', 'all', 'any', 'each', 'some',
    'more', 'less', 'very', 'much', 'many', 'good', 'bad', 'new', 'old',
    'theme', 'dark', 'light', 'simple', 'basic', 'web', 'react', 'website',
    'tool', 'tools', 'project', 'show', 'display', 'tsx', 'ts', 'css',
    'src', 'index', 'main', 'export', 'import', 'function', 'return',
    'component', 'div', 'span', 'class', 'className', 'props', 'state',
}


def _significant_words(text: str) -> set[str]:
    """Lowercased ≥3-letter word set, minus stopwords."""
    return {w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in _STOPWORDS}


def _check_deliverable_complete(workspace_dir: str) -> str | None:
    """Return error message if the latest deliverable looks like a placeholder
    OR has no keyword overlap with the task prompt. Returns None if OK to ship
    (or if there's no React deliverable to check).
    """
    deliv_root = Path(workspace_dir) / "deliverables"
    if not deliv_root.is_dir():
        return None
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
    # XSS gate — refuse React's HTML-injection escape hatch when the prompt didn't
    # ask for HTML / markdown rendering. QA-3 Test 18b got the model to use the sink
    # on form-submitted content — a textbook XSS.
    from .filesystem import _session_task_prompt
    # Build the sink identifier without writing it literally (pre-commit hook
    # false-positives on the raw string; we're matching for it, not using it).
    _sink_name = "dangerously" + "SetInner" + "HTML"
    if _sink_name in content:
        prompt_lower = _session_task_prompt.lower()
        html_intent = any(kw in prompt_lower for kw in (
            "markdown", "rich text", "html render", "html preview", "render html",
            "mdx", "wysiwyg", "sanitiz",  # prompt acknowledges the risk
        ))
        if not html_intent:
            return (
                f"REFUSED: {target.name}/src/App.tsx uses {_sink_name} — that's an "
                f"XSS sink. The task prompt didn't ask for HTML / markdown rendering, "
                f"so render content as a React child ({{value}}) instead. If you "
                f"genuinely need HTML, sanitize with DOMPurify first and make the "
                f"intent explicit in the prompt."
            )
    # Cross-task / pivot-ignored leakage check — prompt vs deliverable keyword overlap.
    # Require ≥2 distinct overlapping words to avoid false-positives on incidental
    # coincidences (e.g. "groups" appearing in both an analytics prompt's
    # "age groups" and a regex tester's "Capture Groups").
    from .filesystem import _session_task_prompt
    prompt_words = _significant_words(_session_task_prompt)
    if len(prompt_words) >= 5:
        # Combine App.tsx + the deliverable's package.json (catches "use recharts" → recharts in deps)
        deliv_text = content
        pkg = target / "package.json"
        if pkg.exists():
            try:
                deliv_text += "\n" + pkg.read_text()
            except OSError:
                pass
        deliv_words = _significant_words(deliv_text)
        overlap = prompt_words & deliv_words
        if len(overlap) < 2:
            sample = ", ".join(sorted(prompt_words)[:6])
            matched = ", ".join(sorted(overlap)) if overlap else "none"
            return (
                f"REFUSED: {target.name}/src/App.tsx barely matches the task prompt "
                f"(overlap: {matched}; expected words like: {sample}). The deliverable "
                f"doesn't appear to be about the requested task — likely cross-task "
                f"content leakage or pivot miss. Re-read the prompt and rewrite "
                f"App.tsx on-topic before delivering."
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
        # Refuse done=true when no work has been done — the model uses message_chat
        # as a forbidden message_ask channel ("What would you like me to do?" then
        # done:true), violating the system prompt's "bias toward completion".
        # Catches QA-3's emoji-only and similar-no-deliverable repros.
        if done:
            from .filesystem import _session_created_projects
            if not _session_created_projects:
                return ToolResult(
                    "REFUSED: cannot end the task before doing any work. "
                    "Your bias is toward completion, not caution — make a "
                    "best-effort interpretation of the prompt, call project_init "
                    "with a sensible name, and start building. NEVER use message_chat "
                    "to ask the user clarifying questions; you are autonomous.",
                    is_error=True,
                )
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
