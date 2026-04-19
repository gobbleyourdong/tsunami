"""Auto-build orchestrator hook.

After a drone writes a source file in a deliverable, the wave runs the
full build pipeline (tsc + vite build + vitest) and interprets the
result. The drone never calls shell_exec or message_result — the wave
decides: pass → task_complete, fail → parse the specific test failure,
record it in plan.md, inject a system_note so the next drone iter sees
exactly what to fix.

Design: message_result is binary — "build succeeded" or
"failed <test>: saw <actual> expected <expected>". The drone's only
job is the write; the wave handles the verification loop.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path


_VITEST_FAIL_RE = re.compile(
    r"(?:FAIL|❯)\s+(?P<file>\S+)\s*>\s*(?P<describe>.+?)\s*>\s*(?P<test>.+?)(?:\n|$)",
    re.MULTILINE,
)
_ASSERT_RE = re.compile(
    r"(?:Expected|expected):\s*(?P<expected>.+?)\n"
    r"(?:Received|toHaveTextContent|saw|to equal):\s*(?P<received>.+?)\n",
    re.IGNORECASE | re.DOTALL,
)


def _parse_vitest_failure(output: str) -> dict | None:
    """Extract the first failing test + its assertion message. Returns
    None if no failure found (build + tests all passed).
    """
    first = _VITEST_FAIL_RE.search(output)
    if not first:
        # Fallback: vitest sometimes prints "Tests: N failed" without the
        # FAIL markers. Look for the first "AssertionError" + surrounding
        # context.
        m = re.search(r"AssertionError[\s\S]{0,600}", output)
        if not m:
            return None
        return {"test": "(unnamed)", "detail": m.group(0)[:500]}

    test_name = first.group("test").strip()
    # Search for matching assertion near the failure
    after = output[first.end(): first.end() + 2000]
    a = _ASSERT_RE.search(after)
    detail = ""
    if a:
        detail = f"expected {a.group('expected').strip()}, got {a.group('received').strip()}"
    else:
        # Show the next 5-10 informative lines after the FAIL header
        snippet = "\n".join(
            ln for ln in after.splitlines()[:12]
            if ln.strip() and "›" not in ln
        )
        detail = snippet[:500]
    return {
        "file": first.group("file").strip(),
        "describe": first.group("describe").strip(),
        "test": test_name,
        "detail": detail,
    }


async def run_build(project_dir: Path, timeout: int = 90) -> dict:
    """Run `npm run build` in project_dir, return structured result.

    Returns: {
      'passed': bool,
      'returncode': int,
      'stdout': str (truncated),
      'failure': dict | None,  # parsed first vitest failure
    }
    """
    proc = await asyncio.create_subprocess_shell(
        "npm run build 2>&1",
        cwd=str(project_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout_b, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {
            "passed": False,
            "returncode": -1,
            "stdout": f"(build timed out after {timeout}s)",
            "failure": {"test": "(build)", "detail": f"timeout after {timeout}s"},
        }
    out = stdout_b.decode("utf-8", errors="replace")
    passed = proc.returncode == 0
    failure = None if passed else _parse_vitest_failure(out)
    # Truncate stdout for log hygiene
    return {
        "passed": passed,
        "returncode": proc.returncode or 0,
        "stdout": out[-4000:] if len(out) > 4000 else out,
        "failure": failure,
    }


def format_failure_for_drone(failure: dict) -> str:
    """One-line-ish human message the drone sees as a system note.
    Leads with the failing test name so the drone targets that edge.
    """
    test = failure.get("test", "(unknown)")
    detail = failure.get("detail", "")
    return f"BUILD FAILED — test '{test}': {detail}"
