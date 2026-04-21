"""Replay regression for pain_advisory_verification_stall (sev 3,
filed in kelp round 13 system_note census).

Round 16 converts the advisory 'VERIFICATION STALL: ... Call
message_result NOW' into a structural force — the next iter's drone
schema is locked to message_result via _loop_forced_tool. Re-uses
the existing loop-guard-force plumbing (schema-gate at L2313,
satisfaction-clear at L3783) so no new surface to maintain.

Fixture: tsunami/tests/replays/verification_stall_force_deliver.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPLAY_PATH = (
    Path(__file__).parent / "replays"
    / "verification_stall_force_deliver.jsonl"
)
AGENT = Path(__file__).parent.parent / "agent.py"


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestVerificationStallReplay:
    @pytest.fixture
    def assertions(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "source_assertion"]

    def test_fixture_well_formed(self, assertions):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        assert meta["slug"] == "verification_stall_force_deliver"
        assert len(assertions) >= 4

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


class TestForceMechanismInvariants:
    """Properties that the reuse of _loop_forced_tool must uphold."""

    @pytest.fixture
    def src(self):
        return AGENT.read_text()

    def test_force_is_set_in_stall_branch_not_advisory(self, src):
        """The conversion moved the enforcement from a system_note to a
        _loop_forced_tool assignment. Verify the assignment is in the
        same conditional block where the advisory USED to be."""
        # The stall branch's log.warning has changed text — find it.
        idx = src.find("Verification stall: build looks done")
        assert idx > 0, "stall branch log message missing"
        # Within the next few hundred chars, _loop_forced_tool must be set.
        window = src[idx:idx + 500]
        assert 'self._loop_forced_tool = "message_result"' in window, (
            "stall branch no longer sets _loop_forced_tool; conversion "
            "may have been reverted"
        )

    def test_no_add_system_note_in_stall_branch(self, src):
        """The old advisory emitted via self.state.add_system_note.
        After conversion that emission is GONE from the stall branch —
        no prompt-level nudge, only structural force."""
        idx = src.find("Verification stall: build looks done")
        window = src[idx:idx + 500]
        assert "VERIFICATION STALL" not in window, (
            "VERIFICATION STALL advisory copy re-introduced in stall branch"
        )
        # Make sure there's no add_system_note between the log and the
        # _loop_forced_tool assignment.
        force_idx = window.find('self._loop_forced_tool = "message_result"')
        assert force_idx > 0
        segment = window[:force_idx]
        assert "add_system_note" not in segment, (
            "stall branch still emits a system_note before the force; "
            "the conversion is incomplete"
        )

    def test_force_satisfaction_path_intact(self, src):
        """When the drone successfully emits message_result (the forced
        tool), _loop_forced_tool must clear so normal schemas resume.
        Without this, the drone would be locked into message_result
        forever after the first stall."""
        assert "self._loop_forced_tool = None" in src
        # The clear happens in the post-exec block when _pf matches the
        # emitted tool name.
        clear_idx = src.find("self._loop_forced_tool = None")
        assert clear_idx > 0
        # Check this clear is inside the satisfaction branch — look for
        # the matching condition within ~500 chars above
        preamble = src[max(0, clear_idx - 800):clear_idx]
        assert "_pf" in preamble
        assert "message_result" in preamble

    def test_force_read_at_step_top(self, src):
        """The top of _step must still read _loop_forced_tool and pass
        it to force_tool. Without this, setting the force has no
        effect on the next iter's schema."""
        assert '_pending_force = getattr(self, "_loop_forced_tool", None)' in src
        assert "force_tool = _pending_force" in src


class TestAuditCensusAfterRound16:
    """Round 16 is the third advisory conversion. Census advisory count
    should be 7 or lower after this commit."""

    def test_advisory_count_after_round_16(self):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "kelp_audit_system_notes_r16",
            Path(__file__).parent.parent.parent
            / "scripts" / "crew" / "kelp" / "audit_system_notes.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["kelp_audit_system_notes_r16"] = mod
        spec.loader.exec_module(mod)
        result = mod.audit()
        # Baseline 10 → round 14 (-1) → round 15 (-1) → round 16 should
        # drop one more. Allow 8 ceiling for mid-session line drift.
        assert result["summary"]["advisory"] <= 8, (
            f"advisory count after round 16 should be ≤ 8 "
            f"(baseline 10, trending down). Got "
            f"{result['summary']['advisory']}."
        )
