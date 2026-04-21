"""Replay regression for pain_advisory_stop_searching +
pain_advisory_stop_running_shell_exec (sev 3, filed in kelp round
13 system_note census).

Round 17 converts four advisories in the 3-in-a-row repeated-tool
branch in tsunami/agent.py to structural _loop_forced_tool
assignments:
  search_web 3x      → force file_write
  shell_exec 3x+err  → force file_edit
  shell_exec 3x+ok   → force message_result
  any other tool 3x  → force message_result

Same conversion pattern as round 16 (verification_stall). This test
anchors each branch's force assignment + the advisory-copy removal.

Fixture: tsunami/tests/replays/stop_searching_force.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "stop_searching_force.jsonl"
)
AGENT = Path(__file__).parent.parent / "agent.py"


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestStopSearchingForceReplay:
    @pytest.fixture
    def assertions(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "source_assertion"]

    def test_fixture_well_formed(self, assertions):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        assert meta["slug"] == "stop_searching_force"
        assert len(assertions) >= 5, (
            "fixture must cover 4 force branches + 1 advisory-removal"
        )

    def test_every_source_assertion_holds(self, assertions):
        src = AGENT.read_text()
        for assertion in assertions:
            desc = assertion["desc"]
            for fragment in assertion.get("required_fragments", []):
                assert fragment in src, (
                    f"source assertion {desc!r} failed: agent.py is "
                    f"missing {fragment!r}"
                )
            for fragment in assertion.get("required_fragments_absent", []):
                assert fragment not in src, (
                    f"source assertion {desc!r} failed: agent.py "
                    f"still contains {fragment!r}"
                )


class TestBranchToForcedToolMapping:
    """Table-driven assertion: each branch name maps to the expected
    forced tool. Makes the intent explicit so a future refactor that
    flips one of these (e.g. search_web→message_result instead of
    file_write) has to update this test with the new mapping."""

    @pytest.fixture
    def src(self):
        return AGENT.read_text()

    def test_search_web_forces_file_write(self, src):
        idx = src.find("Round 17: search_web 3x stall, forcing file_write")
        assert idx > 0, "search_web branch log line missing"
        window = src[idx:idx + 300]
        assert 'self._loop_forced_tool = "file_write"' in window

    def test_shell_exec_with_errors_forces_file_edit(self, src):
        idx = src.find("Round 17: shell_exec 3x with errors, forcing")
        assert idx > 0
        window = src[idx:idx + 300]
        assert 'self._loop_forced_tool = "file_edit"' in window

    def test_shell_exec_no_errors_forces_message_result(self, src):
        idx = src.find("Round 17: shell_exec 3x no errors, forcing")
        assert idx > 0
        window = src[idx:idx + 300]
        assert 'self._loop_forced_tool = "message_result"' in window

    def test_generic_branch_forces_message_result(self, src):
        idx = src.find("Round 17: {repeated_tool} 3x stall, forcing")
        assert idx > 0
        window = src[idx:idx + 300]
        assert 'self._loop_forced_tool = "message_result"' in window


class TestAuditCensusAfterRound17:
    """4 advisories converted in one pass — census should show a bigger
    drop than single-conversion rounds."""

    def test_advisory_count_dropped_by_at_least_two(self):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "kelp_audit_system_notes_r17",
            Path(__file__).parent.parent.parent
            / "scripts" / "crew" / "kelp" / "audit_system_notes.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["kelp_audit_system_notes_r17"] = mod
        spec.loader.exec_module(mod)
        result = mod.audit()
        # Round 16 left it at 8. Round 17 converted 4 sites. Should
        # be ≤ 6.
        assert result["summary"]["advisory"] <= 6, (
            f"round 17 converted 4 advisory sites; census should be "
            f"≤ 6. Got {result['summary']['advisory']}."
        )
