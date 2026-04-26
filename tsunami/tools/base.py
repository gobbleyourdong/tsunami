"""Minimal stub for backward-compat tool inheritance.

The original BaseTool was the agent-loop's tool-registration ABC. With
the agent loop retired in c94b029 (2026-04-26), tools are no longer
auto-registered into a runtime — they're scripts/modules an AI agent
harness calls directly (via Bash, or `python -c "from tsunami.tools.X
import f; f(...)"`).

This stub keeps the surviving tool files' class structure intact
without needing the deleted `TsunamiConfig`. Their actual entry
points (`run` / `call` / module-level functions) are what gets invoked
now, not anything from this base.

If you're refactoring a tool: the cleaner end-state is plain
module-level functions returning plain dicts. The stub is here only
because changing every call site simultaneously isn't worth the
churn.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolResult:
    content: str
    is_error: bool = False

    def __str__(self) -> str:
        return self.content


class BaseTool:
    """Empty stub — was the agent-loop's tool ABC.

    Surviving tools subclass this for backward compat. The actual
    work happens in their module-level helpers or in the subclass's
    own methods, not in anything inherited from this base.
    """

    name: str = ""
    description: str = ""
    concurrent_safe: bool = False

    def __init__(self, config=None):
        self.config = config
