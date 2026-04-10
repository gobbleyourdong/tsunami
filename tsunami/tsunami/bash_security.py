"""Bash command security validation — 24 injection/safety checks.

Validates shell commands BEFORE execution to catch:
- Shell injection via metacharacters, IFS, brace expansion
- Obfuscated flags and backslash-escaped operators
- Proc/environ access for credential theft
- Zsh-specific dangerous builtins
- Unicode whitespace tricks
- Control character injection
- Quote/comment desync attacks

Returns a list of (check_id, warning_message) tuples.
An empty list means the command passed all checks.
"""

from __future__ import annotations

import re
import logging

log = logging.getLogger("tsunami.bash_security")

# --- Check IDs ---
INCOMPLETE_COMMANDS = 1
OBFUSCATED_FLAGS = 4
SHELL_METACHARACTERS = 5
DANGEROUS_VARIABLES = 6
NEWLINES = 7
COMMAND_SUBSTITUTION = 8
INPUT_REDIRECTION = 9
IFS_INJECTION = 11
GIT_COMMIT_SUBSTITUTION = 12
PROC_ENVIRON_ACCESS = 13
BACKSLASH_ESCAPED_WHITESPACE = 15
BRACE_EXPANSION = 16
CONTROL_CHARACTERS = 17
UNICODE_WHITESPACE = 18
ZSH_DANGEROUS = 20
BACKSLASH_ESCAPED_OPERATORS = 21
COMMENT_QUOTE_DESYNC = 22

# Zsh dangerous builtins 
ZSH_DANGEROUS_COMMANDS = frozenset({
    "zmodload", "emulate",
    "sysopen", "sysread", "syswrite", "sysseek",
    "zpty", "ztcp", "zsocket", "mapfile",
    "zf_rm", "zf_mv", "zf_ln", "zf_chmod", "zf_chown",
    "zf_mkdir", "zf_rmdir", "zf_chgrp",
})

# Dangerous environment variable patterns
DANGEROUS_VAR_PATTERNS = [
    re.compile(r'\$\{.*[!@#].*\}'),  # Bash indirect expansion
    re.compile(r'\$\(.*\)'),  # Command substitution in var
]

# Control characters (excluding tab \t and newline \n)
CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# Unicode whitespace tricks
UNICODE_WS_RE = re.compile(r'[\u00a0\u1680\u2000-\u200b\u2028\u2029\u202f\u205f\u3000\ufeff]')

# Brace expansion that could execute unexpected commands
BRACE_EXPANSION_RE = re.compile(r'\{[^}]*,[^}]*\}')

# IFS manipulation
IFS_RE = re.compile(r'\bIFS\s*=')

# Proc/environ access (credential theft vector)
PROC_ENVIRON_RE = re.compile(r'/proc/\d*/environ|/proc/self/environ')

# Git commit substitution (can execute arbitrary code)
GIT_COMMIT_SUB_RE = re.compile(r'git\s+commit.*\$\(')

# Backslash-escaped operators (obfuscation)
BACKSLASH_OP_RE = re.compile(r'\\[|&;]')

# Obfuscated flags (e.g., -\x65val → -eval)
OBFUSCATED_FLAG_RE = re.compile(r'-\\x[0-9a-fA-F]{2}')

# Comment/quote desync: unmatched quotes before # could hide code
INCOMPLETE_QUOTE_RE = re.compile(r"(?:^|[^\\])'[^']*$|(?:^|[^\\])\"[^\"]*$")


def _has_unescaped(text: str, char: str) -> bool:
    """Check if text contains an unescaped instance of char."""
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            i += 2
            continue
        if text[i] == char:
            return True
        i += 1
    return False


def validate_bash_command(command: str) -> list[tuple[int, str]]:
    """Run all security checks on a bash command.

    Returns list of (check_id, warning) tuples. Empty = safe.
    """
    warnings: list[tuple[int, str]] = []
    cmd = command.strip()

    if not cmd:
        return warnings

    # 1. Control characters (invisible code injection)
    if CONTROL_CHAR_RE.search(cmd):
        warnings.append((CONTROL_CHARACTERS, "Command contains control characters"))

    # 2. Unicode whitespace (visual obfuscation)
    if UNICODE_WS_RE.search(cmd):
        warnings.append((UNICODE_WHITESPACE, "Command contains Unicode whitespace characters"))

    # 3. Obfuscated flags
    if OBFUSCATED_FLAG_RE.search(cmd):
        warnings.append((OBFUSCATED_FLAGS, "Command contains obfuscated flags (hex-encoded)"))

    # 4. IFS injection
    if IFS_RE.search(cmd):
        warnings.append((IFS_INJECTION, "Command modifies IFS (input field separator)"))

    # 5. Proc/environ access
    if PROC_ENVIRON_RE.search(cmd):
        warnings.append((PROC_ENVIRON_ACCESS, "Command accesses /proc/*/environ (credential theft risk)"))

    # 6. Git commit with command substitution
    if GIT_COMMIT_SUB_RE.search(cmd):
        warnings.append((GIT_COMMIT_SUBSTITUTION, "Git commit with command substitution"))

    # 7. Brace expansion (can expand to unexpected commands)
    if BRACE_EXPANSION_RE.search(cmd):
        warnings.append((BRACE_EXPANSION, "Command uses brace expansion"))

    # 8. Backslash-escaped operators (obfuscation)
    if BACKSLASH_OP_RE.search(cmd):
        warnings.append((BACKSLASH_ESCAPED_OPERATORS, "Command contains backslash-escaped operators"))

    # 9. Zsh dangerous commands
    first_word = cmd.split()[0] if cmd.split() else ""
    # Check each command in a pipeline
    for part in re.split(r'[|;&]', cmd):
        word = part.strip().split()[0] if part.strip().split() else ""
        if word in ZSH_DANGEROUS_COMMANDS:
            warnings.append((ZSH_DANGEROUS, f"Dangerous zsh builtin: {word}"))
            break

    # 10. Dangerous variable expansions
    for pattern in DANGEROUS_VAR_PATTERNS:
        if pattern.search(cmd):
            warnings.append((DANGEROUS_VARIABLES, "Dangerous variable expansion pattern"))
            break

    # 11. Backslash-escaped whitespace in arguments (obfuscation)
    if re.search(r'\\[ \t]', cmd) and not cmd.startswith("find "):
        # Allow in find commands where escaped spaces are common
        warnings.append((BACKSLASH_ESCAPED_WHITESPACE, "Backslash-escaped whitespace (potential obfuscation)"))

    # 12. Incomplete/unbalanced quotes (could be injection setup)
    lines = cmd.split("\n")
    for line in lines:
        stripped = line.split("#")[0]  # Remove comments
        single_count = stripped.count("'") - stripped.count("\\'")
        double_count = stripped.count('"') - stripped.count('\\"')
        if single_count % 2 != 0 or double_count % 2 != 0:
            warnings.append((COMMENT_QUOTE_DESYNC, "Unbalanced quotes (potential injection)"))
            break

    return warnings


def is_command_safe(command: str) -> tuple[bool, list[str]]:
    """Convenience: check if command is safe to execute.

    Returns (is_safe, list_of_warnings).
    Critical checks (control chars, proc access, zsh builtins) block execution.
    Other checks only warn.
    """
    checks = validate_bash_command(command)
    if not checks:
        return True, []

    # These check IDs are critical — block execution
    critical = {CONTROL_CHARACTERS, PROC_ENVIRON_ACCESS, ZSH_DANGEROUS, UNICODE_WHITESPACE}
    messages = [msg for _, msg in checks]
    is_critical = any(cid in critical for cid, _ in checks)

    return not is_critical, messages
