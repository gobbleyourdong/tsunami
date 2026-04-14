"""CLI slash commands and tab completion.

Slash commands provide quick access to CLI features without
going through the agent. They run synchronously in the CLI loop.

Commands:
  /attach <path>  — inject file content into next prompt
  /detach         — remove all attached files
  /status         — model health, iteration count, tension, context usage
  /trace [N]      — show last N tool calls with timing
  /sessions       — list saved sessions
  /clear          — clear conversation history
  /help           — show available commands

Tab completion is provided via readline integration.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CLIState:
    """State for CLI commands (attached files, trace, etc.)."""
    attached_files: dict[str, str] = field(default_factory=dict)  # path -> content
    trace: list[dict] = field(default_factory=list)  # tool call history
    session_start: float = field(default_factory=time.time)

    def attach(self, path: str) -> str:
        """Attach a file — its content will be injected into the next prompt."""
        expanded = os.path.expanduser(path)
        if not os.path.exists(expanded):
            return f"File not found: {path}"
        try:
            content = open(expanded).read()
            self.attached_files[path] = content
            lines = content.count("\n") + 1
            return f"Attached {path} ({lines} lines)"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def detach(self) -> str:
        """Remove all attached files."""
        count = len(self.attached_files)
        self.attached_files.clear()
        return f"Detached {count} file(s)" if count else "No files attached"

    def get_attachment_block(self) -> str | None:
        """Get attached file content for prompt injection. Clears after use."""
        if not self.attached_files:
            return None
        blocks = []
        for path, content in self.attached_files.items():
            blocks.append(f"[ATTACHED: {path}]\n{content}")
        self.attached_files.clear()
        return "\n\n".join(blocks)

    def record_tool_call(self, tool_name: str, args: dict, duration_ms: float, success: bool):
        """Record a tool call for the trace view."""
        self.trace.append({
            "tool": tool_name,
            "args_preview": str(args)[:80],
            "duration_ms": round(duration_ms, 1),
            "success": success,
            "timestamp": time.time(),
        })
        # Keep last 100
        if len(self.trace) > 100:
            self.trace = self.trace[-100:]


# All slash commands
SLASH_COMMANDS = [
    "/attach", "/detach", "/status", "/trace",
    "/sessions", "/clear", "/help", "/quit",
]


def format_trace(state: CLIState, n: int = 10) -> str:
    """Format the last N tool calls as a trace view."""
    recent = state.trace[-n:]
    if not recent:
        return "No tool calls recorded yet."

    lines = [f"Last {len(recent)} tool calls:"]
    for entry in recent:
        status = "OK" if entry["success"] else "ERR"
        t = time.strftime("%H:%M:%S", time.localtime(entry["timestamp"]))
        lines.append(
            f"  {t} [{status}] {entry['tool']:<20} "
            f"{entry['duration_ms']:>6.0f}ms  {entry['args_preview']}"
        )
    return "\n".join(lines)


def format_status(agent=None, state: CLIState | None = None) -> str:
    """Format agent status: model, iteration, tension, context."""
    lines = ["Status:"]

    if agent:
        lines.append(f"  Model: {getattr(agent, 'config', None) and agent.config.model_name or 'unknown'}")
        lines.append(f"  Iteration: {agent.state.iteration}")
        lines.append(f"  Messages: {len(agent.state.conversation)}")

        # Context usage
        from .compression import estimate_tokens
        tokens = estimate_tokens(agent.state)
        lines.append(f"  Context: ~{tokens:,} tokens")

        # Tool filter phase
        if hasattr(agent, 'tool_filter'):
            phase = agent.tool_filter.detect_phase()
            lines.append(f"  Phase: {phase}")

    if state:
        uptime = time.time() - state.session_start
        m, s = divmod(int(uptime), 60)
        h, m = divmod(m, 60)
        lines.append(f"  Uptime: {h}h {m}m {s}s")
        lines.append(f"  Tool calls: {len(state.trace)}")
        lines.append(f"  Attached files: {len(state.attached_files)}")

    return "\n".join(lines)


def format_help() -> str:
    """Format the help text for slash commands."""
    return """Available commands:
  /attach <path>  — Attach file content to next prompt
  /detach         — Remove all attached files
  /status         — Show agent status (model, iteration, tension, context)
  /trace [N]      — Show last N tool calls with timing (default: 10)
  /sessions       — List saved sessions
  /clear          — Clear conversation history
  /help           — Show this help
  /quit           — Exit"""


def setup_tab_completion():
    """Set up readline tab completion for slash commands.

    Falls back silently if readline is not available (Windows).
    """
    try:
        import readline

        def completer(text: str, state: int):
            matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(text)]
            if state < len(matches):
                return matches[state]
            return None

        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")
        return True
    except ImportError:
        return False


def handle_slash_command(
    command: str,
    cli_state: CLIState,
    agent=None,
) -> str | None:
    """Handle a slash command. Returns response text, or None if not a command."""
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/attach":
        if not arg:
            return "Usage: /attach <path>"
        return cli_state.attach(arg)

    elif cmd == "/detach":
        return cli_state.detach()

    elif cmd == "/status":
        return format_status(agent, cli_state)

    elif cmd == "/trace":
        n = int(arg) if arg.isdigit() else 10
        return format_trace(cli_state, n)

    elif cmd == "/help":
        return format_help()

    elif cmd == "/clear":
        if agent:
            agent.state.conversation = agent.state.conversation[:2]  # keep system + user
            return "Conversation cleared (kept system prompt + original request)"
        return "No active agent"

    elif cmd == "/quit":
        return "__QUIT__"

    return None  # not a slash command
