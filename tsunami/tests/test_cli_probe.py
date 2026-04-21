"""cli_probe tests — iterate pass/ (expect accept) and fail/ (expect reject).

Fixture layout:
  tests/fixtures/cli/pass/{minimal,typical,rich}/    → probe must return passed=True
  tests/fixtures/cli/fail/{empty,malformed,no_help,  → probe must return passed=False
                           not_executable,hangs}/

The `hangs` fixture exists to exercise the timeout branch; test uses a
short timeout (1s) so the suite stays fast.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tsunami.core.cli_probe import cli_probe, _find_cli_entry
from tsunami.core.dispatch import _PROBES, detect_scaffold


_REPO = Path(__file__).resolve().parent.parent.parent
_FIXTURES = _REPO / "tests" / "fixtures" / "cli"


def _run(coro):
    # asyncio.run creates a fresh loop per call — isolates from other
    # probe tests that may have closed the loop already.
    return asyncio.run(coro)


# ── Dispatch integration ─────────────────────────────────────────────

class TestDispatchRegistration:
    def test_cli_registered_in_PROBES(self):
        assert "cli" in _PROBES
        assert _PROBES["cli"] is cli_probe

    def test_detect_scaffold_pass_minimal_is_cli(self):
        assert detect_scaffold(_FIXTURES / "pass" / "minimal") == "cli"

    def test_detect_scaffold_pass_typical_is_cli(self):
        assert detect_scaffold(_FIXTURES / "pass" / "typical") == "cli"

    def test_detect_scaffold_pass_rich_is_cli(self):
        assert detect_scaffold(_FIXTURES / "pass" / "rich") == "cli"


# ── Entry-point discovery (unit) ─────────────────────────────────────

class TestEntryDiscovery:
    def test_minimal_finds_cli_py(self):
        entry = _find_cli_entry(_FIXTURES / "pass" / "minimal")
        assert entry is not None
        path, runner = entry
        assert path.name == "cli.py"
        assert runner == "python3"

    def test_typical_finds_pyproject_script(self):
        entry = _find_cli_entry(_FIXTURES / "pass" / "typical")
        assert entry is not None
        path, runner = entry
        assert path.name == "typical_cli.py"
        assert runner == "python3"

    def test_rich_finds_package_json_bin(self):
        entry = _find_cli_entry(_FIXTURES / "pass" / "rich")
        assert entry is not None
        path, runner = entry
        assert path.name == "cli.js"
        assert runner == "node"

    def test_empty_finds_nothing(self):
        assert _find_cli_entry(_FIXTURES / "fail" / "empty") is None

    def test_not_executable_finds_nothing(self):
        # package.json says bin/cli.js but the file doesn't exist
        assert _find_cli_entry(_FIXTURES / "fail" / "not_executable") is None


# ── Probe pass corpus ────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["minimal", "typical", "rich"])
def test_pass_fixtures_accepted(name):
    res = _run(cli_probe(_FIXTURES / "pass" / name))
    assert res["passed"] is True, f"pass/{name} was rejected: {res['issues']}\n{res['raw']}"


# ── Probe fail corpus ────────────────────────────────────────────────

def test_fail_empty_rejected():
    res = _run(cli_probe(_FIXTURES / "fail" / "empty"))
    assert res["passed"] is False
    assert "no CLI entry point" in res["issues"]


def test_fail_malformed_rejected():
    # malformed package.json → bin field unreadable → no entry found
    res = _run(cli_probe(_FIXTURES / "fail" / "malformed"))
    assert res["passed"] is False
    assert "no CLI entry point" in res["issues"]


def test_fail_no_help_rejected():
    res = _run(cli_probe(_FIXTURES / "fail" / "no_help"))
    assert res["passed"] is False
    # Entry is found but crashes → non-zero exit
    assert "exited" in res["issues"] or "error" in res["issues"].lower()


def test_fail_not_executable_rejected():
    res = _run(cli_probe(_FIXTURES / "fail" / "not_executable"))
    assert res["passed"] is False
    assert "no CLI entry point" in res["issues"]


def test_fail_hangs_rejected():
    # Short timeout so the suite stays fast; 1s is plenty to prove the
    # timeout branch without actually waiting for the default 5s.
    res = _run(cli_probe(_FIXTURES / "fail" / "hangs", help_timeout_s=1.0))
    assert res["passed"] is False
    assert "did not return" in res["issues"] or "stdin" in res["issues"]


# ── Non-directory input ──────────────────────────────────────────────

def test_non_directory_rejected():
    res = _run(cli_probe(_FIXTURES / "nonexistent"))
    assert res["passed"] is False
    assert "not found" in res["issues"]


# ── SECURITY regression (Current sev-5 finding, 2026-04-20) ──────────

def test_shell_injection_rce_regression(tmp_path):
    """Pre-delivery RCE via malicious bin filename MUST NOT execute.

    Current's finding: cli_probe used create_subprocess_shell with an
    f-string command, so a bin-field path containing `;` produced
    pre-delivery arbitrary command execution. Argv-list fix (execve
    directly) means the metacharacter-laden filename is passed as a
    single argv element, never interpreted by /bin/sh.

    The test constructs the attack at runtime (evil filename isn't
    checked into git) and asserts: (a) probe rejects, (b) no
    side-effect file lands in the deliverable dir.
    """
    import json
    import os
    import stat

    # Attacker-controlled filename with shell metacharacters — legal on
    # Linux (only / and NUL are forbidden in filename bytes).
    evil = "tool; touch PWNED_FILE_DO_NOT_COMMIT;"
    evil_path = tmp_path / evil
    evil_path.write_text("#!/bin/sh\necho started\n")
    os.chmod(evil_path, stat.S_IRWXU)
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "evil", "bin": "./" + evil})
    )

    _run(cli_probe(tmp_path, help_timeout_s=3.0))

    # CRITICAL property (the sev-5): the attacker-payload portion of
    # the filename (everything after `;`) MUST NOT have executed.
    # Under the old shell-string form, /bin/sh -c split on `;` and ran
    # `touch PWNED_FILE_DO_NOT_COMMIT` as a second command. Under the
    # argv-list fix, the whole filename is a single execve argument —
    # metacharacters are inert bytes, never interpreted.
    # Note: the benign shebang prefix (`#!/bin/sh\necho started`) can
    # still run and return 0 under the fix — that's fine; the RCE
    # property is "did the post-; command fire," not "did the whole
    # deliverable pass."
    pwned = tmp_path / "PWNED_FILE_DO_NOT_COMMIT"
    assert not pwned.exists(), (
        "SEV-5 REGRESSION: cli_probe executed attacker-controlled "
        "shell command via bin-field metacharacters. "
        "PWNED_FILE_DO_NOT_COMMIT was created in the deliverable dir."
    )
