"""Hook system — user-defined pre/post callbacks on agent events.

Hooks are registered in config and fire on events like PreToolUse, PostToolUse,
SessionStart, etc. They can modify tool input, block execution, or inject context.

Hook types:
- command: Run a shell script, pass event data as JSON on stdin
- function: In-process Python callback (registered at runtime)

Hooks are loaded from:
1. workspace/.hooks.json (project hooks)
2. ~/.tsunami/hooks.json (user hooks)
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("tsunami.hooks")

# Hook timeout
DEFAULT_HOOK_TIMEOUT = 30  # seconds


class HookEvent(str, Enum):
    """Events that can trigger hooks."""
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    PRE_COMPACT = "PreCompact"
    POST_COMPACT = "PostCompact"
    NOTIFICATION = "Notification"
    STOP = "Stop"


class HookOutcome(str, Enum):
    SUCCESS = "success"
    BLOCKING = "blocking"
    NON_BLOCKING_ERROR = "non_blocking_error"
    CANCELLED = "cancelled"


@dataclass
class HookResult:
    """Result from a hook execution."""
    outcome: HookOutcome = HookOutcome.SUCCESS
    message: str = ""
    additional_context: str = ""  # injected into model context
    updated_input: dict | None = None  # modified tool args (PreToolUse only)
    blocking_error: str = ""


@dataclass
class HookConfig:
    """Configuration for a single hook."""
    type: str  # "command" or "function"
    matcher: str = ""  # tool name filter (empty = match all)
    command: str = ""  # for type="command"
    timeout: int = DEFAULT_HOOK_TIMEOUT
    callback: Callable | None = None  # for type="function"


class HookRegistry:
    """Registry of hooks organized by event."""

    def __init__(self):
        self._hooks: dict[str, list[HookConfig]] = {}
        self._function_hooks: dict[str, list[HookConfig]] = {}

    def register(self, event: str | HookEvent, hook: HookConfig):
        """Register a hook for an event."""
        key = event.value if isinstance(event, HookEvent) else event
        if hook.type == "function":
            self._function_hooks.setdefault(key, []).append(hook)
        else:
            self._hooks.setdefault(key, []).append(hook)

    def register_function(self, event: str | HookEvent, callback: Callable,
                          matcher: str = "", timeout: int = DEFAULT_HOOK_TIMEOUT):
        """Convenience: register an in-process function hook."""
        key = event.value if isinstance(event, HookEvent) else event
        hook = HookConfig(type="function", matcher=matcher, timeout=timeout, callback=callback)
        self._function_hooks.setdefault(key, []).append(hook)

    def get_hooks(self, event: str | HookEvent, tool_name: str = "") -> list[HookConfig]:
        """Get all hooks for an event, filtered by matcher."""
        key = event.value if isinstance(event, HookEvent) else event
        all_hooks = self._hooks.get(key, []) + self._function_hooks.get(key, [])
        if not tool_name:
            return all_hooks
        return [h for h in all_hooks if not h.matcher or h.matcher == tool_name]

    def clear_session_hooks(self):
        """Clear function hooks (session-scoped). Keep command hooks (config-based)."""
        self._function_hooks.clear()

    def load_from_file(self, path: str | Path):
        """Load hooks from a JSON config file.

        Format: {"PreToolUse": [{"matcher": "shell_exec", "type": "command", "command": "..."}]}
        """
        p = Path(path)
        if not p.exists():
            return

        try:
            data = json.loads(p.read_text())
            for event_name, hooks_list in data.items():
                if not isinstance(hooks_list, list):
                    continue
                for hd in hooks_list:
                    if not isinstance(hd, dict):
                        continue
                    hook = HookConfig(
                        type=hd.get("type", "command"),
                        matcher=hd.get("matcher", ""),
                        command=hd.get("command", ""),
                        timeout=hd.get("timeout", DEFAULT_HOOK_TIMEOUT),
                    )
                    self.register(event_name, hook)
            log.info(f"Loaded hooks from {p}")
        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f"Failed to load hooks from {p}: {e}")

    @property
    def count(self) -> int:
        total = sum(len(v) for v in self._hooks.values())
        total += sum(len(v) for v in self._function_hooks.values())
        return total


async def execute_hook(hook: HookConfig, event_data: dict) -> HookResult:
    """Execute a single hook and return its result."""
    if hook.type == "function" and hook.callback:
        return await _exec_function_hook(hook, event_data)
    elif hook.type == "command" and hook.command:
        return await _exec_command_hook(hook, event_data)
    else:
        return HookResult(outcome=HookOutcome.NON_BLOCKING_ERROR, message=f"Invalid hook type: {hook.type}")


async def execute_hooks(registry: HookRegistry, event: str | HookEvent,
                        event_data: dict, tool_name: str = "") -> list[HookResult]:
    """Execute all hooks for an event. Returns results in order.

    If any hook returns BLOCKING, subsequent hooks still run but the
    blocking error is propagated.
    """
    hooks = registry.get_hooks(event, tool_name)
    if not hooks:
        return []

    results = []
    for hook in hooks:
        try:
            result = await execute_hook(hook, event_data)
            results.append(result)
        except Exception as e:
            results.append(HookResult(
                outcome=HookOutcome.NON_BLOCKING_ERROR,
                message=f"Hook crashed: {e}",
            ))

    return results


async def _exec_command_hook(hook: HookConfig, event_data: dict) -> HookResult:
    """Execute a shell command hook.

    pass event data as JSON on stdin.
    Exit code 0 = success, 2 = blocking error, other = non-blocking.
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            hook.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        input_json = json.dumps(event_data).encode()
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_json),
                timeout=hook.timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return HookResult(
                outcome=HookOutcome.NON_BLOCKING_ERROR,
                message=f"Hook timed out after {hook.timeout}s: {hook.command}",
            )

        stdout_str = stdout.decode(errors="replace").strip()
        stderr_str = stderr.decode(errors="replace").strip()

        if proc.returncode == 0:
            # Try to parse structured output
            updated_input = None
            if stdout_str:
                try:
                    parsed = json.loads(stdout_str)
                    if isinstance(parsed, dict):
                        updated_input = parsed.get("updated_input")
                except json.JSONDecodeError:
                    pass
            return HookResult(
                outcome=HookOutcome.SUCCESS,
                message=stdout_str,
                updated_input=updated_input,
            )
        elif proc.returncode == 2:
            return HookResult(
                outcome=HookOutcome.BLOCKING,
                blocking_error=stderr_str or stdout_str or "Hook blocked execution",
            )
        else:
            return HookResult(
                outcome=HookOutcome.NON_BLOCKING_ERROR,
                message=stderr_str or f"Hook exited with code {proc.returncode}",
            )

    except Exception as e:
        return HookResult(
            outcome=HookOutcome.NON_BLOCKING_ERROR,
            message=f"Hook execution error: {e}",
        )


async def _exec_function_hook(hook: HookConfig, event_data: dict) -> HookResult:
    """Execute an in-process function hook."""
    if hook.callback is None:
        return HookResult(outcome=HookOutcome.NON_BLOCKING_ERROR, message="No callback")

    try:
        if asyncio.iscoroutinefunction(hook.callback):
            result = await asyncio.wait_for(
                hook.callback(event_data),
                timeout=hook.timeout,
            )
        else:
            result = hook.callback(event_data)

        if isinstance(result, HookResult):
            return result
        elif isinstance(result, dict):
            return HookResult(
                outcome=HookOutcome(result.get("outcome", "success")),
                message=result.get("message", ""),
                updated_input=result.get("updated_input"),
            )
        else:
            return HookResult(outcome=HookOutcome.SUCCESS)

    except asyncio.TimeoutError:
        return HookResult(
            outcome=HookOutcome.NON_BLOCKING_ERROR,
            message=f"Function hook timed out after {hook.timeout}s",
        )
    except Exception as e:
        return HookResult(
            outcome=HookOutcome.NON_BLOCKING_ERROR,
            message=f"Function hook error: {e}",
        )
