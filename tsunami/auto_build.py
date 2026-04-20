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

# tsc emits errors like:
#   src/App.tsx(49,9): error TS2322: Type '...' is not assignable to type 'IntrinsicAttributes & NavbarProps'.
#     Property 'menuOpen' does not exist on type 'IntrinsicAttributes & NavbarProps'.
# We care about the specific prop name + the component type name so we can
# tell the drone "read THIS component, not all of them" — breaks the
# read-spiral pattern observed 2026-04-20 on audit_run v4.
_TSC_LINE_RE = re.compile(
    r"^(?P<file>\S+\.tsx?)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<msg>.+)$",
    re.MULTILINE,
)
_TSC_MISSING_PROP_RE = re.compile(
    r"Property '(?P<prop>[A-Za-z_][A-Za-z0-9_]*)' does not exist on type "
    r"'[^']*?(?P<component>[A-Z][A-Za-z0-9_]+)Props'"
)


def _parse_tsc_failure(output: str) -> dict | None:
    """Parse the first tsc error. Prefer 'missing prop' errors since those
    drive the drone to read the specific component file, breaking the
    read-spiral pattern.
    """
    mp = _TSC_MISSING_PROP_RE.search(output)
    if mp:
        prop = mp.group("prop")
        comp = mp.group("component")
        file_hit = _TSC_LINE_RE.search(output)
        where = ""
        if file_hit:
            where = f" at {file_hit.group('file')}:{file_hit.group('line')}"
        return {
            "test": "tsc",
            "detail": (
                f"App.tsx passed prop '{prop}' to <{comp}> but {comp}Props "
                f"doesn't declare '{prop}'{where}. Read src/components/"
                f"{comp}.tsx to see its real props, then rewrite App.tsx "
                f"with matching prop names. Do NOT read every component — "
                f"the error names exactly which one is wrong."
            ),
        }
    line_hit = _TSC_LINE_RE.search(output)
    if line_hit:
        return {
            "test": "tsc",
            "detail": (
                f"{line_hit.group('file')}:{line_hit.group('line')} "
                f"{line_hit.group('code')}: {line_hit.group('msg')[:240]}"
            ),
        }
    return None


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
    # Try tsc first — type errors appear before vitest even starts and drive
    # the specific "read component X" nudge that avoids read-spirals.
    failure = None
    if not passed:
        failure = _parse_tsc_failure(out) or _parse_vitest_failure(out)
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
