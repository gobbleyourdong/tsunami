"""Bash-command safety gate — stub.

Originally a policy gate that classifies shell commands as safe / unsafe
(rm -rf /, curl piped to bash, fork-bomb patterns, credential exfil, etc.)
and returns a (bool, list[str]) tuple. The real implementation was never
committed. This stub returns (True, []) for everything so the ShellExec
tool continues to work.

Signature contract: `is_command_safe(command: str) -> tuple[bool, list[str]]`.
Return (True, []) to allow the command, (False, [reason]) to block.

If you need to harden this later, the single call site in
`tsunami/tools/shell.py::ShellExec._execute_impl` runs every command
through here — wire up real heuristics and the tool picks it up.
"""
from __future__ import annotations


def is_command_safe(command: str) -> tuple[bool, list[str]]:
    """No-op pass-through. Returns (True, []) = allow the command."""
    return True, []
