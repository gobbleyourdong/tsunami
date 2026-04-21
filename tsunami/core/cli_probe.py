"""CLI delivery gate — `--help` smoke + entry-point discovery.

The CLI scaffold class covers anything shipped as a command-line tool:
Python click/argparse/typer entry points, Node commander/yargs binaries,
POSIX shebang scripts. This probe is intentionally minimal — it proves
the deliverable is *invokable* (entry point exists, runs without crashing,
emits non-empty `--help` within 5s).

Failure modes caught:
  - No entry point registered (no `bin` in package.json, no
    `[project.scripts]` in pyproject.toml, no conventional `bin/` or
    `src/cli.{py,ts}` / `cli.py` / `main.py`)
  - Entry file exists but is broken (import error, syntax error → non-zero
    exit on `--help`)
  - Entry file hangs on `--help` (missing argparse setup, waiting on stdin)
  - `--help` emits nothing (argparse configured but no help text wired)
  - package.json broken JSON / pyproject.toml broken

Not caught (out of scope for a delivery gate):
  - Actual command correctness (use a probe-caller's fixture test for that)
  - Performance / memory (separate benchmark harness)
  - Installability across OS/python versions
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
from pathlib import Path

from ._probe_common import result, skip


# ── Entry-point discovery ────────────────────────────────────────────

def _node_bin_entry(project_dir: Path, pkg: dict) -> tuple[Path, str] | None:
    """Resolve package.json `bin` field to a (path, runner) pair."""
    bin_field = pkg.get("bin")
    if not bin_field:
        return None
    candidates: list[str] = []
    if isinstance(bin_field, str):
        candidates.append(bin_field)
    elif isinstance(bin_field, dict):
        candidates.extend(v for v in bin_field.values() if isinstance(v, str))
    for c in candidates:
        p = (project_dir / c).resolve()
        if p.is_file():
            return p, _pick_runner(p)
    return None


def _python_script_entry(project_dir: Path) -> tuple[Path, str] | None:
    """Resolve pyproject.toml `[project.scripts]` to a runnable python file.

    Crude TOML parser — looks for `name = "module.path:func"` inside
    either [project.scripts] or [tool.poetry.scripts] sections, then
    maps module.path to a file on disk under project root or src/.
    """
    pyproj = project_dir / "pyproject.toml"
    if not pyproj.is_file():
        return None
    try:
        text = pyproj.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    in_scripts = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_scripts = s in ("[project.scripts]", "[tool.poetry.scripts]")
            continue
        if not in_scripts or not s or s.startswith("#"):
            continue
        m = re.match(
            r'([a-zA-Z_][\w-]*)\s*=\s*["\']([a-zA-Z_][\w.]*):([a-zA-Z_][\w]*)["\']',
            s,
        )
        if not m:
            continue
        module = m.group(2)
        rel = Path(*module.split(".")).with_suffix(".py")
        for layout in (project_dir / rel,
                       project_dir / "src" / rel,
                       project_dir / rel.with_suffix("") / "__main__.py"):
            if layout.is_file():
                return layout, "python3"
    return None


_CONVENTIONAL = (
    "bin/cli", "bin/cli.py", "bin/main", "bin/main.py",
    "src/cli.py", "src/cli.ts", "src/cli.js", "src/main.py",
    "cli.py", "main.py",
)


def _conventional_entry(project_dir: Path) -> tuple[Path, str] | None:
    for rel in _CONVENTIONAL:
        p = project_dir / rel
        if p.is_file():
            return p, _pick_runner(p)
    # bin/ dir with any executable regular file
    bin_dir = project_dir / "bin"
    if bin_dir.is_dir():
        for child in sorted(bin_dir.iterdir()):
            if child.is_file():
                return child, _pick_runner(child)
    return None


def _pick_runner(p: Path) -> str:
    """Pick a shell-runnable command prefix for this file.

    Shebang'd files run as-is (the shebang chooses the interpreter).
    Extension-typed files get an explicit interpreter so they run even
    without +x bit.
    """
    suffix = p.suffix.lower()
    if suffix == ".py":
        return "python3"
    if suffix in (".ts",):
        return "npx tsx"
    if suffix in (".js", ".mjs", ".cjs"):
        return "node"
    # No/other extension — trust shebang, run directly
    return ""


def _find_cli_entry(project_dir: Path) -> tuple[Path, str] | None:
    """Try each discovery path in priority order."""
    pkg_path = project_dir / "package.json"
    if pkg_path.is_file():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pkg = None
        if pkg is not None:
            e = _node_bin_entry(project_dir, pkg)
            if e:
                return e
    e = _python_script_entry(project_dir)
    if e:
        return e
    return _conventional_entry(project_dir)


# ── Probe ────────────────────────────────────────────────────────────

async def cli_probe(
    project_dir: Path,
    help_timeout_s: float = 5.0,
    task_text: str = "",
) -> dict:
    """Entry exists + `<runner> <entry> --help` → exit 0 + non-empty stdout.

    `task_text` kept in the signature for uniformity with the other probes
    (dispatch.py calls every probe as `await probe(project_dir)`).
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return result(False, f"project dir not found: {project_dir}")

    entry = _find_cli_entry(project_dir)
    if entry is None:
        return result(
            False,
            "no CLI entry point found. Checked: package.json `bin`, "
            "pyproject.toml [project.scripts] / [tool.poetry.scripts], "
            "conventional paths (bin/cli*, src/cli.*, cli.py, main.py), "
            "and bin/ directory contents.",
        )

    entry_path, runner = entry
    rel = entry_path.relative_to(project_dir) if entry_path.is_relative_to(project_dir) else entry_path

    # SECURITY (sev-5 patch, 2026-04-21): argv-list form via
    # asyncio.create_subprocess_exec instead of create_subprocess_shell(f_string).
    # The old cmd-string went through /bin/sh -c, which interprets ;,
    # $, backticks, &, |, etc. in filenames as shell metacharacters. A
    # malicious package.json `bin: "./tool; echo $SECRET > leaked.txt;"`
    # achieved pre-delivery RCE with env-var exfiltration. Argv form
    # calls execve directly so metacharacters pass verbatim. (Current
    # finding: cli_probe_shell_injection_rce, sev 5.)
    if runner:
        argv = runner.split() + [str(entry_path), "--help"]
    else:
        # No runner = shebang-direct invocation. Require +x up front so
        # the failure is a clear probe rejection rather than a timeout.
        import os as _os
        if not _os.access(str(entry_path), _os.X_OK):
            return result(
                False,
                f"CLI entry `{rel}` is not executable and has no known "
                "runner (no shebang or unrecognized extension). Either "
                "set +x or declare via package.json bin / pyproject.",
            )
        argv = [str(entry_path), "--help"]

    try:
        # stdin=DEVNULL — deliverable MUST NOT inherit parent stdin.
        # start_new_session=True puts the child in its own process group
        # so we can killpg the whole subtree on timeout.
        spawn = asyncio.create_subprocess_exec
        proc = await spawn(
            *argv,
            cwd=str(project_dir),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    except (FileNotFoundError, PermissionError) as e:
        return result(
            False,
            f"CLI entry cannot be executed: {type(e).__name__}: {e}. "
            f"Tried argv={argv!r}.",
        )
    except Exception as e:
        return result(False, f"failed to spawn argv={argv!r}: {e}")

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=help_timeout_s,
        )
    except asyncio.TimeoutError:
        # Kill the whole process group — shell wrapper + its children —
        # so time.sleep / blocking I/O in the python/node child doesn't
        # keep the suite waiting.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                proc.kill()
            except Exception:
                pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except (asyncio.TimeoutError, Exception):
            pass
        return result(
            False,
            f"`{' '.join(argv)}` did not return within {help_timeout_s}s — "
            "CLI likely hangs on stdin or mis-wires argparse.",
        )

    out = (stdout or b"").decode("utf-8", errors="replace")
    err = (stderr or b"").decode("utf-8", errors="replace")

    if proc.returncode != 0:
        return result(
            False,
            f"`--help` exited {proc.returncode} (expected 0). "
            "CLI likely has an import error, syntax error, or "
            "argparse misconfiguration.",
            raw=(err or out)[:600],
        )

    if not out.strip() and not err.strip():
        return result(
            False,
            "`--help` exited 0 but emitted no output. "
            "CLI is invokable but has no help text wired.",
        )

    # Success — capture entry path + first few help lines for logs
    help_snippet = (out or err).strip().splitlines()[:8]
    return result(
        True,
        "",
        raw=f"entry={rel}\nrunner={runner or '(shebang)'}\n\n" + "\n".join(help_snippet),
    )


__all__ = ["cli_probe", "_find_cli_entry"]
