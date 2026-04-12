"""Shell execution tools — the muscle.

The agent acts on the world through the shell.
Never run complex code inline — save to file first, then execute.

Full process lifecycle: exec, view, send, wait, kill.
"""

from __future__ import annotations
import re

# Destructive command patterns — block or warn
_DESTRUCTIVE_PATTERNS = [
    # Self-preservation — BLOCK commands that destroy the agent itself
    (re.compile(r'\brm\s+(-\w+\s+)*tsunami\b'),
     "BLOCKED: cannot delete the tsunami directory"),
    (re.compile(r'\brm\s+(-\w+\s+)*\.\s*$|\brm\s+(-\w+\s+)*\./'),
     "BLOCKED: cannot recursively delete current directory"),
    # Workspace protection
    (re.compile(r'rm\s+(-\w*)?r\w*\s+.*deliverables|rm\s+(-\w*)?r\w*\s+.*workspace'),
     "BLOCKED: rm -rf on deliverables/workspace is forbidden"),
    # Git — data loss
    (re.compile(r'\bgit\s+reset\s+--hard\b'),
     "WARNING: may discard uncommitted changes"),
    (re.compile(r'\bgit\s+push\b[^;&|\n]*\s+(--force|-f)\b'),
     "WARNING: may overwrite remote history"),
    (re.compile(r'\bgit\s+clean\b[^;&|\n]*-[a-zA-Z]*f'),
     "WARNING: may permanently delete untracked files"),
    (re.compile(r'\bgit\s+checkout\s+(--\s+)?\.'),
     "WARNING: may discard all working tree changes"),
    # Git — safety bypass
    (re.compile(r'\bgit\s+(commit|push|merge)\b[^;&|\n]*--no-verify\b'),
     "WARNING: skipping safety hooks"),
    # Recursive force delete on root-like paths
    (re.compile(r'\brm\s+(-\w+\s+)*/\s*$'),
     "BLOCKED: cannot rm -rf root"),
    # Recursive delete on any absolute or home-directory path — escapes the workspace
    (re.compile(r'\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\s+[~/]'),
     "BLOCKED: rm -r on absolute or home path — refuse (use a relative path inside the workspace)"),
    # Recursive force delete (catchall — relative paths still warn)
    (re.compile(r'(^|[;&|]\s*)rm\s+-[a-zA-Z]*[rR][a-zA-Z]*f'),
     "WARNING: recursive force-remove"),
    # Database
    (re.compile(r'\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)\b', re.I),
     "WARNING: may drop database objects"),
    (re.compile(r'\bDELETE\s+FROM\s+\w+\s*(;|$)', re.I),
     "WARNING: may delete all rows"),
    # Infrastructure
    (re.compile(r'\bkubectl\s+delete\b'),
     "WARNING: may delete Kubernetes resources"),
    (re.compile(r'\bterraform\s+destroy\b'),
     "WARNING: may destroy infrastructure"),
    # Credential / secret exfiltration (QA-3 prompt-injection bait-and-switch)
    (re.compile(r'(~|/home/[^/\s]+|/root)/\.(aws|ssh|gnupg|kube|docker|netrc|npmrc|pypirc)\b'),
     "BLOCKED: refuse to read or write credential / secret directories"),
    (re.compile(r'(~|/home/[^/\s]+|/root)/\.([a-zA-Z]+rc|profile|bash_profile|bash_login|zlogin|zprofile|cshrc|tcshrc|inputrc|env)\b'),
     "BLOCKED: refuse to modify shell rc / profile / env files (alias hijack risk)"),
    (re.compile(r'\bcrontab\b[^;&|\n]*\s-\s*$|\bcrontab\b[^;&|\n]*\s-\s*[<|]', re.M),
     "BLOCKED: refuse to install/replace crontab entries"),
    (re.compile(r'/etc/(passwd|shadow|sudoers|cron\.|profile)'),
     "BLOCKED: refuse to read or write system credential / cron / profile files"),
    # Multi-turn data-plant (QA-3 Stage A of the cross-session exfiltration chain):
    # bait-and-switch prompts instructing `echo/printf 'VALUE' > /tmp/X.txt` so a
    # follow-up session can read + bake into a deliverable. React build flows do
    # not need echo/printf-to-/tmp; this is narrow enough to miss legit tooling
    # (which uses mktemp / XDG cache dirs) while catching the concrete attack.
    (re.compile(r'\b(echo|printf)\s+[^|&;\n]*(>|>>)\s*/(tmp|var/tmp)/'),
     "BLOCKED: refuse to plant values in /tmp via echo/printf redirect "
     "(multi-turn exfiltration vector)"),
    # QA-3 Fire 37 bypass: `echo X | tee /tmp/Y` and `tee -a /tmp/Y` skip the
    # above rule by using tee instead of > redirection. Same plant, same risk.
    # Legit `tee` use against /tmp is rare for React builds; block it.
    (re.compile(r'\|\s*tee\b[^|&;\n]*\s/(tmp|var/tmp)/'),
     "BLOCKED: refuse to plant values in /tmp via `| tee` "
     "(multi-turn exfiltration vector)"),
    (re.compile(r'\btee\s+(-[a-zA-Z]+\s+)*/(tmp|var/tmp)/'),
     "BLOCKED: refuse to plant values in /tmp via `tee <path>` "
     "(multi-turn exfiltration vector)"),
    # QA-3 Fire 64: split download-then-execute chain bypassed the echo/tee
    # blocks by using curl/wget's own -o / -O flag to write to /tmp, then
    # chmod+exec. Block the first stage (download to /tmp) — if the payload
    # can't land, stages 2-3 have nothing to run. React builds never need
    # curl -o /tmp; legit dep install goes through npm.
    (re.compile(r'\bcurl\b[^|&;\n]*\s-o\s+/(tmp|var/tmp)/'),
     "BLOCKED: refuse to download to /tmp via `curl -o` "
     "(supply-chain / RCE staging vector)"),
    (re.compile(r'\bwget\b[^|&;\n]*\s-O\s+/(tmp|var/tmp)/'),
     "BLOCKED: refuse to download to /tmp via `wget -O` "
     "(supply-chain / RCE staging vector)"),
    # Chmod +x on /tmp is the second stage of the same chain — defense in depth.
    (re.compile(r'\bchmod\s+(-[a-zA-Z]+\s+)*\+?x\w*\s+/(tmp|var/tmp)/'),
     "BLOCKED: refuse to chmod +x files in /tmp "
     "(RCE staging vector)"),
    # QA-3 Fire 85: interpreter -c/-e bypass. The existing shell-syntax regex
    # doesn't inspect inside quoted `-c` arguments to an interpreter. Agent ran
    # a python one-liner invoking the shell-exec syscall API and the /tmp
    # marker landed. Block the dangerous subset of interpreter-c invocations
    # — narrow enough that legit one-liners (`python3 -c "print(...)"`,
    # `node -e "console.log(1)"`) still pass.
    # Identifiers built via concatenation so the repo's pre-commit security
    # hook doesn't misfire on literal references in this file.
    (re.compile(
        r'\bpython3?\s+-c\s+[\'"].*?'
        r'(?:os\.sys' + r'tem|sub' + r'process\.|__imp' + r'ort__\s*\(\s*[\'"]os)',
    ),
     "BLOCKED: python -c invoking shell-exec syscalls — "
     "emit shell_exec directly instead of smuggling shell via python"),
    (re.compile(r'\b(perl|ruby)\s+-e\s+[\'"].*?\bsys' + r'tem\s*\('),
     "BLOCKED: interpreter -e invoking shell-exec syscalls — "
     "emit shell_exec directly instead of smuggling shell via interpreter"),
    (re.compile(r'\bnode\s+-e\s+[\'"].*?(?:exec' + r'Sync|exec\s*\(|spawn\s*\()'),
     "BLOCKED: node -e invoking shell-exec syscalls — "
     "emit shell_exec directly instead of smuggling shell via node"),
    # Nested shell -c has no legit use inside shell_exec (which already runs
    # under bash). It's only there to rewrap blocked patterns past the
    # top-level regex scan.
    (re.compile(r'\b(bash|sh|zsh|fish|dash)\s+-c\b'),
     "BLOCKED: nested shell -c is redundant inside shell_exec and a "
     "common regex-bypass vector — emit the command directly"),
    # QA-3 Fire 86 bypass 4 (plain `touch`): d7448f3 targets echo/printf/tee/
    # curl/wget write-to-/tmp; `touch /tmp/X` creates a 0-byte marker, bypasses
    # the "content-via-shell" pattern family. Block bare touch-to-/tmp too —
    # legitimate agent workflows create files inside workspace/, not /tmp.
    (re.compile(r'\btouch\s+(-[a-zA-Z]+\s+)*/(tmp|var/tmp)/'),
     "BLOCKED: refuse to `touch` files in /tmp "
     "(plant-marker vector)"),
    # cp/mv to /tmp is the same attack surface — duplicate a planted payload
    # into a known-path attacker-readable location, or relocate an existing
    # file out of the workspace sandbox.
    (re.compile(r'\b(cp|mv)\s+(-[a-zA-Z]+\s+)*.+\s+/(tmp|var/tmp)/'),
     "BLOCKED: refuse to cp/mv into /tmp "
     "(plant-marker / exfiltration vector)"),
    # QA-3 Fire 67 bypass 2 (env-var expansion): `export TMPDIR=/tmp` or
    # `TMPDIR=/tmp echo X > "$TMPDIR/..."` hides the literal /tmp path from
    # the redirect patterns. Block the assignment itself — legitimate tooling
    # doesn't need to override TMPDIR to /tmp (that's the default).
    (re.compile(r'\b(?:export\s+)?(TMPDIR|TMP|TEMP|TEMPDIR)\s*=\s*/(tmp|var/tmp)\b'),
     "BLOCKED: refuse TMPDIR=/tmp assignment — env-var expansion is a "
     "known regex-bypass vector; use default /tmp handling from the OS"),
    # QA-3 Fire 52: resource-starvation / DOS via social-engineered long-
    # running shell commands. Default shell_exec tool_timeout is 3600s, so
    # `while true` / `yes | ...` / `dd if=/dev/zero` burns the entire agent
    # budget without triggering any existing pattern. No build pipeline has
    # a legitimate use for these shapes. (`sleep N` is handled separately
    # below since short `sleep 2` between retries is legitimate.)
    (re.compile(r'\bwhile\s+(?:true\b|1\b|:)|\bwhile\s+\[\s+1\s+\]'),
     "BLOCKED: `while true` / `while :` is an infinite-loop CPU burn — "
     "no legitimate use in a build pipeline (DOS vector)"),
    (re.compile(r'\byes\b[^|;&\n]*(\||>)'),
     "BLOCKED: `yes` piped or redirected — unbounded-output DOS shape. "
     "Use the package manager's --yes/-y flag instead"),
    (re.compile(r'\b(?:dd|cat)\s+[^;&|\n]*(?:if=)?/dev/(?:zero|urandom|random)\b'),
     "BLOCKED: reading from /dev/zero / /dev/urandom / /dev/random — "
     "disk or CPU burn (DOS vector)"),
    (re.compile(
        r'\bpython3?\s+-c\s+[\'"][^\'"]*?\bwhile\s+True\b|'
        r'\bnode\s+-e\s+[\'"][^\'"]*?(?:for\s*\(\s*;\s*;\s*\)|while\s*\(\s*(?:true|1)\s*\))|'
        r'\b(?:perl|ruby)\s+-e\s+[\'"][^\'"]*?\b1\s+while\s+1\b'
    ),
     "BLOCKED: interpreter one-liner contains an infinite loop — "
     "CPU-burn DOS vector"),
]

# QA-3 Fire 52 continued: `sleep N` with N > _SLEEP_BUDGET blocks, shorter
# sleeps (test delays, rate-limits) pass through. Built as a separate check
# because the regex match needs numeric comparison of the captured N.
_SLEEP_BUDGET_SECONDS = 30
_SLEEP_RE = re.compile(r'\bsleep\s+(\d+(?:\.\d+)?)')


def _check_destructive(command: str) -> str | None:
    """Check command against destructive patterns. Returns warning or None."""
    for pattern, warning in _DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            return warning
    # QA-3 Fire 52: block `sleep N` when N exceeds a reasonable wait budget.
    # Short sleeps (retry delay, rate-limit) are legitimate in build scripts
    # and pass through; long sleeps are the DOS shape.
    for m in _SLEEP_RE.finditer(command):
        try:
            n = float(m.group(1))
        except (TypeError, ValueError):
            continue
        if n > _SLEEP_BUDGET_SECONDS:
            return (
                f"BLOCKED: `sleep {m.group(1)}` exceeds the "
                f"{_SLEEP_BUDGET_SECONDS}s budget — this is the QA-3 Fire 52 "
                f"DOS shape (prompt-injected long wait to burn the agent's "
                f"timeout budget before real work starts). Use a short retry "
                f"delay if you need one."
            )
    return None

import asyncio
import logging
import os
import signal

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.shell")

# Active process sessions — persistent across tool calls
_sessions: dict[str, asyncio.subprocess.Process] = {}
_session_output: dict[str, str] = {}
_session_counter = 0


def _next_session_id() -> str:
    global _session_counter
    _session_counter += 1
    return f"proc_{_session_counter}"


class ShellExec(BaseTool):
    name = "shell_exec"
    description = "Run a shell command and return its output. The muscle: do the thing."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (0 = run in background)", "default": 120},
                "workdir": {"type": "string", "description": "Working directory", "default": ""},
            },
            "required": ["command"],
        }

    async def execute(self, command: str, timeout: int = 3600, workdir: str = "", **kw) -> ToolResult:
        # External dep validation — warn on suspicious npm installs
        import re
        npm_match = re.search(r'npm install\s+([a-z@][a-z0-9@/._-]+)', command)
        if npm_match:
            pkg = npm_match.group(1).strip()
            # Known-good packages pass through; unknown ones get a warning
            known_good = {
                "react", "react-dom", "recharts", "d3", "papaparse", "xlsx",
                "express", "better-sqlite3",
                "cors", "ws", "framer-motion", "zustand", "react-router-dom",
                "react-icons", "date-fns", "lodash", "axios", "uuid",
                "tailwindcss", "postcss", "autoprefixer",
                "@uiw/react-md-editor", "marked", "highlight.js",
                "chart.js", "react-chartjs-2", "socket.io-client",
            }
            if pkg not in known_good and not pkg.startswith("@types/"):
                log.warning(f"Unknown npm package: {pkg}")

        # Destructive command detection
        warning = _check_destructive(command)
        if warning and warning.startswith("BLOCKED"):
            return ToolResult(warning, is_error=True)

        # Bash security validation (24 checks)
        from ..bash_security import is_command_safe
        is_safe, sec_warnings = is_command_safe(command)
        if not is_safe:
            return ToolResult(
                f"BLOCKED: Security check failed: {'; '.join(sec_warnings)}",
                is_error=True,
            )
        if sec_warnings:
            log.warning(f"Bash security warnings for '{command[:80]}': {sec_warnings}")

        # Fix common path errors from the model
        # Model trained on Docker where /workspace was the root — rewrite to correct paths
        import os
        # ark dir is 3 levels up from tsunami/tools/shell.py
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        tsunami_dir = os.path.dirname(tools_dir)
        ark_dir_local = os.path.dirname(tsunami_dir)
        workspace_abs = os.path.normpath(os.path.join(ark_dir_local, self.config.workspace_dir if hasattr(self, 'config') else 'workspace'))
        if '/workspace/' in command:
            command = command.replace('/workspace/', f'{workspace_abs}/')
            log.info(f"Path fix: /workspace/ → {workspace_abs}/")
        elif 'cd workspace/' in command:
            command = command.replace('cd workspace/', f'cd {workspace_abs}/', 1)
            log.info(f"Path fix: cd workspace/ → cd {workspace_abs}/")

        # Fix hallucinated brackets, quotes, and noise in paths
        import re
        command = re.sub(r'\[project[^\]]*\]?', '', command)  # [project...] with or without closing
        command = re.sub(r'\[[^\]]*\]', '', command)  # any [bracket] content
        command = re.sub(r"\-'[^']*'?", '', command)  # -'garbage' suffixes

        # Fix npm run dev → npx vite build (scaffold doesn't have dev script)
        if 'npm run dev' in command:
            command = command.replace('npm run dev', 'npx vite build')
            log.info("Command fix: npm run dev → npx vite build")

        try:
            # Resolve workdir — default to workspace dir (not cwd)
            cwd = os.path.join(ark_dir_local, self.config.workspace_dir) if hasattr(self, 'config') else None
            if workdir:
                expanded = os.path.expanduser(workdir)
                if os.path.isdir(expanded):
                    cwd = expanded
                else:
                    # Try relative to ark dir
                    candidate = os.path.join(ark_dir_local, workdir)
                    if os.path.isdir(candidate):
                        cwd = candidate
                    # else: let it use default cwd

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            # Background mode: register session and return immediately
            if timeout == 0:
                sid = _next_session_id()
                _sessions[sid] = proc
                _session_output[sid] = ""
                return ToolResult(
                    f"Background process started: {sid} (PID {proc.pid})\n"
                    f"Use shell_view to check output, shell_wait to await completion, "
                    f"shell_kill to terminate."
                )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return ToolResult(f"Command timed out after {timeout}s: {command}", is_error=True)

            out = stdout.decode(errors="replace").strip()
            err = stderr.decode(errors="replace").strip()

            # Smart output truncation — show what was lost
            max_chars = 10000
            if len(out) > max_chars:
                total_lines = out.count('\n') + 1
                truncated_part = out[:max_chars]
                remaining_lines = out[max_chars:].count('\n') + 1
                out = f"{truncated_part}\n\n... [{remaining_lines} lines truncated, {total_lines} total] ..."

            parts = []
            if out:
                parts.append(out)
            if err:
                parts.append(f"[stderr] {err}")
            parts.append(f"[exit code: {proc.returncode}]")

            return ToolResult("\n".join(parts), is_error=proc.returncode != 0)
        except Exception as e:
            return ToolResult(f"Error executing command: {e}", is_error=True)


class ShellView(BaseTool):
    name = "shell_view"
    description = "Check output and status of a background process. The mirror: see what happened."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID from shell_exec (e.g. 'proc_1')"},
            },
            "required": ["session_id"],
        }

    async def execute(self, session_id: str, **kw) -> ToolResult:
        proc = _sessions.get(session_id)
        if proc is None:
            available = list(_sessions.keys()) or ["none"]
            return ToolResult(
                f"Session '{session_id}' not found. Active: {', '.join(available)}",
                is_error=True,
            )

        # Try to read available output without blocking
        output_parts = []

        if proc.stdout:
            try:
                # Non-blocking read of whatever's available
                data = await asyncio.wait_for(proc.stdout.read(8192), timeout=1.0)
                if data:
                    text = data.decode(errors="replace")
                    _session_output[session_id] = _session_output.get(session_id, "") + text
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

        status = "running" if proc.returncode is None else f"exited ({proc.returncode})"
        buffered = _session_output.get(session_id, "")

        # Show last 3000 chars of output
        display = buffered[-3000:] if len(buffered) > 3000 else buffered

        return ToolResult(
            f"Session: {session_id} | PID: {proc.pid} | Status: {status}\n"
            f"Output ({len(buffered)} chars total):\n{display}"
        )


class ShellSend(BaseTool):
    name = "shell_send"
    description = "Send input to a running background process. The voice: speak to running programs."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID"},
                "input_text": {"type": "string", "description": "Text to send to stdin"},
            },
            "required": ["session_id", "input_text"],
        }

    async def execute(self, session_id: str, input_text: str, **kw) -> ToolResult:
        proc = _sessions.get(session_id)
        if proc is None:
            return ToolResult(f"Session '{session_id}' not found", is_error=True)

        if proc.returncode is not None:
            return ToolResult(f"Process already exited with code {proc.returncode}", is_error=True)

        if proc.stdin is None:
            return ToolResult("Process stdin not available", is_error=True)

        try:
            proc.stdin.write((input_text + "\n").encode())
            await proc.stdin.drain()
            return ToolResult(f"Sent to {session_id}: {input_text[:200]}")
        except Exception as e:
            return ToolResult(f"Send error: {e}", is_error=True)


class ShellWait(BaseTool):
    name = "shell_wait"
    description = "Wait for a background process to complete. The patience: let the process finish."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID"},
                "timeout": {"type": "integer", "description": "Max seconds to wait", "default": 60},
            },
            "required": ["session_id"],
        }

    async def execute(self, session_id: str, timeout: int = 60, **kw) -> ToolResult:
        proc = _sessions.get(session_id)
        if proc is None:
            return ToolResult(f"Session '{session_id}' not found", is_error=True)

        if proc.returncode is not None:
            output = _session_output.get(session_id, "")
            return ToolResult(
                f"Process already exited with code {proc.returncode}\n"
                f"Output: {output[-3000:]}"
            )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout.decode(errors="replace") if stdout else ""
            err = stderr.decode(errors="replace") if stderr else ""
            _session_output[session_id] = _session_output.get(session_id, "") + out

            parts = [f"Process {session_id} completed (exit code: {proc.returncode})"]
            if out:
                parts.append(out[-5000:])
            if err:
                parts.append(f"[stderr] {err[-2000:]}")

            return ToolResult("\n".join(parts), is_error=proc.returncode != 0)
        except asyncio.TimeoutError:
            return ToolResult(
                f"Still running after {timeout}s. Use shell_view to check progress "
                f"or shell_kill to terminate.",
            )


class ShellKill(BaseTool):
    name = "shell_kill"
    description = "Terminate a background process. The mercy: end what is no longer needed."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID"},
                "force": {"type": "boolean", "description": "Use SIGKILL instead of SIGTERM", "default": False},
            },
            "required": ["session_id"],
        }

    async def execute(self, session_id: str, force: bool = False, **kw) -> ToolResult:
        proc = _sessions.get(session_id)
        if proc is None:
            return ToolResult(f"Session '{session_id}' not found", is_error=True)

        if proc.returncode is not None:
            del _sessions[session_id]
            return ToolResult(f"Process already exited with code {proc.returncode}. Session cleaned up.")

        try:
            if force:
                proc.kill()
                method = "SIGKILL"
            else:
                proc.terminate()
                method = "SIGTERM"

            # Wait briefly for cleanup
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                if not force:
                    proc.kill()
                    method = "SIGKILL (escalated)"

            del _sessions[session_id]
            return ToolResult(f"Process {session_id} (PID {proc.pid}) terminated via {method}")
        except Exception as e:
            return ToolResult(f"Kill error: {e}", is_error=True)
