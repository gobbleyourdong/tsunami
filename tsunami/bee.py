"""Bee — a lightweight agent worker powered by the 2B model.

A bee is a mini agent loop: it receives a task, has access to tools
(file_read, shell_exec, match_grep, etc.), and runs autonomously
until it completes or hits a turn limit.

Unlike the queen (27B full agent), bees are:
- Fast (~100 tok/s on 2B)
- Cheap (small context, no vision)
- Disposable (no session persistence)
- Parallel (multiple bees run simultaneously)

The queen dispatches bees for:
- Reading/analyzing multiple files
- Running independent shell commands
- Searching across a codebase
- Any batch of homogeneous tasks
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

log = logging.getLogger("tsunami.bee")

BEE_ENDPOINT = os.environ.get("TSUNAMI_BEE_ENDPOINT", "http://localhost:8092")
MAX_TURNS = 10  # safety cap per bee
BEE_TIMEOUT = 30  # seconds per LLM call


@dataclass
class BeeResult:
    """Result from a bee's work."""
    task: str
    success: bool
    output: str
    tool_calls: int = 0
    turns: int = 0
    elapsed_ms: float = 0
    error: str = ""


# Tools available to bees (subset of queen's tools)
BEE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read a file's content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "offset": {"type": "integer", "description": "Start line", "default": 0},
                    "limit": {"type": "integer", "description": "Max lines", "default": 200},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": "Run a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_grep",
            "description": "Search file contents by regex",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "directory": {"type": "string", "description": "Where to search", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Report your final answer",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "description": "Your findings/answer"},
                },
                "required": ["result"],
            },
        },
    },
]


async def _execute_bee_tool(name: str, args: dict, workdir: str) -> str:
    """Execute a tool on behalf of a bee. Runs locally (not via LLM)."""
    if name == "file_read":
        path = args.get("path", "")
        if not path or not isinstance(path, str):
            return "Error: path parameter required (string)"
        if len(path) > 500:
            return "Error: path too long (max 500 chars)"
        # Block sensitive files
        basename = Path(path).name.lower()
        sensitive = {'.env', '.env.local', '.env.production', '.env.development',
                     '.netrc', '.npmrc', '.pypirc', 'credentials', 'credentials.json',
                     'id_rsa', 'id_ed25519', 'id_ecdsa', '.htpasswd', 'shadow',
                     'token', 'token.json', '.git-credentials'}
        if basename in sensitive or basename.startswith('.env'):
            return f"BLOCKED: bees cannot read sensitive files ({basename})"
        p = Path(path) if Path(path).is_absolute() else Path(workdir) / path
        # Sandbox: bees can only read within workdir
        try:
            resolved = str(p.resolve())
            if not resolved.startswith(str(Path(workdir).resolve())):
                return f"BLOCKED: bees can only read files within the project directory"
        except (OSError, ValueError):
            return f"Error: invalid path {path}"
        if not p.exists():
            return f"File not found: {path}"
        # Binary detection — check first 512 bytes for null bytes
        try:
            with open(p, "rb") as f:
                head = f.read(512)
            if b"\x00" in head:
                size_kb = p.stat().st_size / 1024
                return f"Binary file ({size_kb:.0f} KB) — cannot read as text: {path}"
        except OSError:
            pass
        # Size gate — skip huge files
        try:
            file_size = p.stat().st_size
        except OSError:
            return f"Cannot access: {path}"
        if file_size > 256 * 1024:
            return f"File too large ({file_size // 1024} KB). Use offset/limit or grep instead."
        try:
            text = p.read_text(errors="replace")
        except (OSError, PermissionError) as e:
            return f"Cannot read {path}: {e}"
        lines = text.splitlines()
        offset = args.get("offset", 0)
        limit = args.get("limit", 200)
        selected = lines[offset:offset + limit]
        return "\n".join(selected)[:4000]

    elif name == "shell_exec":
        cmd = args.get("command", "")
        if not cmd or not isinstance(cmd, str):
            return "Error: command parameter required (string)"
        if len(cmd) > 2000:
            return "Error: command too long (max 2000 chars)"
        # Bash security — bees get stricter checks than queen
        import re
        # Block any rm -rf on root or broad paths
        if re.search(r'\brm\s+(-\w*)?r\w*f?\s+/', cmd):
            return "BLOCKED: bees cannot run recursive rm on root paths"
        # Block network exfiltration tools
        network_cmds = re.compile(r'\b(curl|wget|nc|ncat|netcat|socat|ssh|scp|rsync|ftp|sftp|telnet)\b')
        if network_cmds.search(cmd):
            return "BLOCKED: bees cannot use network tools (curl, wget, nc, ssh, etc.)"
        # Block interpreters (can bypass all other checks via import)
        interp_cmds = re.compile(r'\b(python3?|python2|node|ruby|perl|php|lua|java\b|scala)\s')
        if interp_cmds.search(cmd):
            return "BLOCKED: bees cannot launch interpreters (use tools directly instead)"
        # Block process backgrounding (escape from timeout)
        if re.search(r'\bnohup\b|&\s*$|\bdisown\b', cmd):
            return "BLOCKED: bees cannot background processes"
        # Block env dumping (can leak API keys, tokens, credentials)
        if re.search(r'^\s*(env|printenv|set|export)\s*$|^\s*(env|printenv)\b', cmd):
            return "BLOCKED: bees cannot dump environment variables"
        # Block git credential/config access (can leak tokens)
        if re.search(r'\bgit\s+(config|credential)\b', cmd):
            return "BLOCKED: bees cannot access git config/credentials"
        # Block file writes via shell (redirects, sed -i, tee, dd, mv, cp, etc.)
        if re.search(r'(?<!\|)\s*>\s*[^&]|>>', cmd):  # output redirect (not pipe)
            return "BLOCKED: bees are read-only (cannot redirect output to files)"
        if re.search(r'\bsed\s+.*-i\b|\btee\b|\bdd\b|\bmv\b|\bcp\b|\bmkdir\b|\btouch\b|\bchmod\b|\bchown\b|\binstall\b|\bln\b', cmd):
            return "BLOCKED: bees are read-only (cannot modify filesystem via shell)"
        from .bash_security import is_command_safe
        from .tools.shell import _check_destructive
        destructive = _check_destructive(cmd)
        if destructive and destructive.startswith("BLOCKED"):
            return destructive
        is_safe, warnings = is_command_safe(cmd)
        if not is_safe:
            return f"BLOCKED: {'; '.join(warnings)}"
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=workdir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            out = stdout.decode(errors="replace")[:4000]
            if stderr:
                out += f"\n[stderr] {stderr.decode(errors='replace')[:1000]}"
            return out
        except asyncio.TimeoutError:
            return "Command timed out after 30s"
        except Exception as e:
            return f"Error: {e}"

    elif name == "match_grep":
        pattern = args.get("pattern", "")
        if not pattern or not isinstance(pattern, str):
            return "Error: pattern parameter required (string)"
        if len(pattern) > 500:
            return "Error: pattern too long (max 500 chars)"
        directory = args.get("directory", workdir)
        if not Path(directory).is_absolute():
            directory = str(Path(workdir) / directory)
        # Sandbox: grep restricted to workdir
        try:
            if not str(Path(directory).resolve()).startswith(str(Path(workdir).resolve())):
                return "BLOCKED: bees can only search within the project directory"
        except (OSError, ValueError):
            return "Error: invalid directory"
        try:
            proc = await asyncio.create_subprocess_exec(
                "grep", "-rn", "--include=*.py", "--include=*.ts",
                "--include=*.js", "--include=*.md",
                "--exclude-dir=node_modules", "--exclude-dir=.git",
                "--exclude-dir=__pycache__", "--exclude-dir=models",
                pattern, directory,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            return stdout.decode(errors="replace")[:4000] or "No matches"
        except Exception as e:
            return f"Grep error: {e}"

    elif name == "done":
        return args.get("result", "")

    return f"Unknown tool: {name}"


async def run_bee(
    task: str,
    workdir: str = ".",
    endpoint: str = BEE_ENDPOINT,
    max_turns: int = MAX_TURNS,
    system_prompt: str = "",
) -> BeeResult:
    """Run a single bee agent loop.

    The bee gets a task, can use tools, and runs until it calls
    'done' or hits the turn limit.
    """
    start = time.time()

    # Guard: empty or whitespace-only tasks fail fast
    if not task or not task.strip():
        return BeeResult(
            task=task or "", success=False, output="",
            error="Empty task", elapsed_ms=0,
        )

    # Sanitize control characters from task (null bytes, ANSI escapes)
    import re as _re
    task = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', task)
    task = _re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', task)  # strip ANSI escapes

    if not system_prompt:
        system_prompt = (
            "You are a focused worker agent. Complete the task using the tools available. "
            "When you have the answer, call the 'done' tool with your result. "
            "Be concise. Do not explain your process — just deliver the result."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    tool_calls = 0
    turns = 0

    async with httpx.AsyncClient(timeout=BEE_TIMEOUT) as client:
        for turn in range(max_turns):
            turns = turn + 1

            try:
                resp = await client.post(
                    f"{endpoint}/v1/chat/completions",
                    json={
                        "model": "qwen",
                        "messages": messages,
                        "tools": BEE_TOOLS,
                        "tool_choice": "auto",
                        "max_tokens": 1024,
                        "temperature": 0.3,
                    },
                    headers={"Authorization": "Bearer not-needed"},
                )

                if resp.status_code != 200:
                    return BeeResult(
                        task=task, success=False, output="",
                        error=f"HTTP {resp.status_code}",
                        turns=turns, elapsed_ms=(time.time() - start) * 1000,
                    )

                data = resp.json()
                choice = data["choices"][0]
                msg = choice["message"]

                # Check for tool calls
                if msg.get("tool_calls"):
                    tc = msg["tool_calls"][0]
                    func = tc["function"]
                    name = func["name"]
                    raw_args = func.get("arguments", "{}")
                    if isinstance(raw_args, dict):
                        args = raw_args
                    elif isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            args = {}
                    else:
                        args = {}

                    tool_calls += 1

                    # Done tool = terminate
                    if name == "done":
                        return BeeResult(
                            task=task, success=True,
                            output=args.get("result", ""),
                            tool_calls=tool_calls, turns=turns,
                            elapsed_ms=(time.time() - start) * 1000,
                        )

                    # Execute tool
                    result = await _execute_bee_tool(name, args, workdir)

                    # Add to conversation
                    messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": msg["tool_calls"]})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                else:
                    # Text response — treat as final answer
                    content = msg.get("content", "").strip()
                    if content:
                        return BeeResult(
                            task=task, success=True, output=content,
                            tool_calls=tool_calls, turns=turns,
                            elapsed_ms=(time.time() - start) * 1000,
                        )

            except httpx.TimeoutException:
                return BeeResult(
                    task=task, success=False, output="",
                    error="Timeout", turns=turns,
                    elapsed_ms=(time.time() - start) * 1000,
                )
            except Exception as e:
                return BeeResult(
                    task=task, success=False, output="",
                    error=str(e)[:200], turns=turns,
                    elapsed_ms=(time.time() - start) * 1000,
                )

    return BeeResult(
        task=task, success=False, output="",
        error=f"Hit turn limit ({max_turns})",
        turns=turns, tool_calls=tool_calls,
        elapsed_ms=(time.time() - start) * 1000,
    )


async def run_swarm(
    tasks: list[str],
    workdir: str = ".",
    max_concurrent: int = 4,
    endpoint: str = BEE_ENDPOINT,
    system_prompt: str = "",
) -> list[BeeResult]:
    """Run multiple bees in parallel with concurrency control.

    The queen calls this to dispatch work to the hive.
    """
    sem = asyncio.Semaphore(max_concurrent)
    start = time.time()

    async def _run(task: str) -> BeeResult:
        async with sem:
            return await run_bee(task, workdir, endpoint, system_prompt=system_prompt)

    results = await asyncio.gather(*[_run(t) for t in tasks])
    elapsed = (time.time() - start) * 1000

    succeeded = sum(1 for r in results if r.success)
    total_tool_calls = sum(r.tool_calls for r in results)
    log.info(
        f"Swarm complete: {succeeded}/{len(results)} succeeded, "
        f"{total_tool_calls} tool calls, {elapsed:.0f}ms"
    )

    return list(results)


def format_swarm_results(results: list[BeeResult]) -> str:
    """Format swarm results for the queen to consume."""
    lines = [f"swarm: {len(results)} bees dispatched"]
    for i, r in enumerate(results):
        status = "ok" if r.success else "FAIL"
        lines.append(f"\n[bee {i}] {status} ({r.turns} turns, {r.tool_calls} tools, {r.elapsed_ms:.0f}ms)")
        if r.output:
            lines.append(r.output[:500])
        if r.error:
            lines.append(f"  error: {r.error}")
    return "\n".join(lines)
