"""Regression tests for the sev-5 shell-injection class across the probe
surface (2026-04-21 consolidator patch).

Current's cli_probe finding established the pattern: probes that build a
subprocess command via f-string and pass it to
`asyncio.create_subprocess_shell` take attacker-controlled filename
components through `/bin/sh -c`, producing pre-delivery RCE. The patch
moved every probe spawn to argv-list via `asyncio.create_subprocess_exec`
(directly in cli_probe + electron_probe, shared via
`_probe_common.spawn_child` for extension/gamedev/sse/ws/server/openapi).

These tests build minimum-viable evil fixtures programmatically and
assert: no side-effect file landed in the temp dir. The probe may pass
or fail — irrelevant — the CRITICAL property is that `/bin/sh` wasn't
in the path to interpret filename/build_cmd metacharacters.
"""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

import pytest

from tsunami.core._probe_common import spawn_child, terminate_child


def _run(coro):
    return asyncio.run(coro)


async def _spawn_and_wait(cmd, cwd):
    """Single coroutine so spawn + wait + terminate share one event
    loop (asyncio subprocess waiters are loop-scoped)."""
    proc = await spawn_child(cmd, cwd=cwd)
    try:
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    finally:
        await terminate_child(proc)


def test_spawn_child_no_rce_via_shell_metachars_in_string_cmd(tmp_path: Path):
    """spawn_child given a string command with shell metacharacters
    must NOT execute the post-; payload. shlex.split produces argv;
    exec form passes metacharacters as argument bytes."""
    evil_cmd = "echo hello ; touch PWNED_SPAWN_CHILD ;"
    _run(_spawn_and_wait(evil_cmd, tmp_path))
    pwned = tmp_path / "PWNED_SPAWN_CHILD"
    assert not pwned.exists(), (
        "SEV-5 REGRESSION: _probe_common.spawn_child executed shell "
        "metacharacters in the command string. PWNED_SPAWN_CHILD was "
        "created — meaning /bin/sh interpreted the `;` as a command "
        "separator."
    )


def test_spawn_child_accepts_argv_list_unchanged(tmp_path: Path):
    """List input skips shlex entirely — metacharacter bytes pass
    verbatim as a single argument to the runner."""
    evil_argv = ["echo", "tag ; touch PWNED_ARGV_FORM ;"]
    _run(_spawn_and_wait(evil_argv, tmp_path))
    pwned = tmp_path / "PWNED_ARGV_FORM"
    assert not pwned.exists(), (
        "SEV-5 REGRESSION: argv-list form still let the shell interpret "
        "the `;`. create_subprocess_exec must have been routed through "
        "/bin/sh somewhere."
    )


def test_spawn_child_empty_cmd_raises(tmp_path: Path):
    """Empty or whitespace-only command string → ValueError, not a
    silent npm-in-cwd side-effect."""
    with pytest.raises(ValueError):
        _run(spawn_child("   ", cwd=tmp_path))


# ── electron_probe regression ────────────────────────────────────────

def test_electron_probe_no_rce_via_build_cmd(tmp_path: Path):
    """electron_probe used to build its subprocess command via
    f"{build_cmd} 2>&1" and pass through /bin/sh. Now argv-form via
    shlex.split + exec. Attacker-controlled build_cmd must not run
    post-; payload."""
    import json

    from tsunami.core.electron_probe import electron_probe

    # Build a minimal valid package.json so the probe gets past the
    # early-return checks and actually tries to spawn the build.
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "x",
        "main": "index.js",
        "dependencies": {"electron": "^28"},
    }))
    (tmp_path / "index.js").write_text("// noop")

    evil_cmd = "echo hi ; touch PWNED_ELECTRON_PROBE ;"
    _run(electron_probe(tmp_path, build_cmd=evil_cmd, timeout_s=5))

    pwned = tmp_path / "PWNED_ELECTRON_PROBE"
    assert not pwned.exists(), (
        "SEV-5 REGRESSION: electron_probe executed build_cmd "
        "metacharacters through /bin/sh. Migrate to argv-form."
    )


# ── cli_probe already has a test in test_cli_probe.py ────────────────
# (test_shell_injection_rce_regression — commit 17f29cc)
# This file exists to extend the coverage class-wide.
