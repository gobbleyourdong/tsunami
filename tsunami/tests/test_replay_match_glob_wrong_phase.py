"""Replay regression for pain_match_glob_wrong_phase (severity 2).

Anchors the dispatch-reject elif branch for match_glob / match_grep
in tsunami/agent.py. The generic "Available: [sorted list]" dump
doesn't tell the drone what to do; the tailored error names file_read
with an explicit path as the right next action, and flags that
scaffold_params / data/*.json are already inlined so search is
wasted context.

Trace source: 3 sessions 2026-04-20 (1776733458 silent-blade,
1776733868 neon-drift, 1776735631). Each one emitted match_glob /
match_grep in WRITE phase and got the generic reject.

Fixture: tsunami/tests/replays/match_glob_wrong_phase.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "match_glob_wrong_phase.jsonl"
)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestMatchGlobRejectSource:
    """Source-level assertions on agent.py. The reject-message branch
    is applied at dispatch time; full behavioral boot of Agent would
    need a live model and tool registry. Source checks protect the
    specific strings a future refactor might drop."""

    @pytest.fixture
    def src(self):
        return (Path(__file__).parent.parent / "agent.py").read_text()

    def test_fixture_well_formed(self):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        checks = [e for e in events if e["kind"] == "reject_message_check"]
        assert meta["slug"] == "match_glob_wrong_phase"
        assert len(checks) == 2, \
            "fixture must cover both match_glob and match_grep"

    def test_agent_has_match_glob_branch(self, src):
        assert 'elif tool_call.name in ("match_glob", "match_grep"):' in src, (
            "agent.py dispatch reject lost the match_glob/match_grep "
            "branch. Restore the tailored helper so search-tool "
            "misroutes point the drone at file_read with an explicit path."
        )

    def test_reject_message_contains_required_fragments(self, src):
        """Every fragment in every reject_message_check must appear in
        the agent.py source inside the match_glob/match_grep branch."""
        events = _load_replay(REPLAY_PATH)
        checks = [e for e in events if e["kind"] == "reject_message_check"]
        shared_required = {
            frag
            for check in checks
            for frag in check["reject_must_contain"]
            if frag not in ("match_glob", "match_grep")
        }
        for fragment in shared_required:
            assert fragment in src, (
                f"agent.py reject for match_glob/match_grep is missing "
                f"{fragment!r}. Restore the branch or the anchor test "
                f"corpus is out of sync."
            )

    def test_reject_references_inlined_prompt(self, src):
        """The whole reason this pain exists is that the drone is
        searching for files whose structure is already in the system
        prompt. The reject must say so — 'inlined' / 'system prompt'
        is the explanation that should dislodge the pattern."""
        idx = src.find('elif tool_call.name in ("match_glob", "match_grep"):')
        assert idx > 0
        body = src[idx:idx + 1200]
        assert "inlined" in body
        assert "system prompt" in body
        assert "file_read" in body
        assert "explicit path" in body


class TestBranchOrdering:
    """The match_glob branch must come after message_chat and
    shell_exec in the elif chain — both earlier pains have tighter,
    more specific logic that should run first. A subtle re-ordering
    bug could mask one of those earlier fixes."""

    def test_match_glob_branch_after_shell_branch(self):
        src = (Path(__file__).parent.parent / "agent.py").read_text()
        shell_idx = src.find('elif tool_call.name == "shell_exec":')
        match_idx = src.find(
            'elif tool_call.name in ("match_glob", "match_grep"):'
        )
        chat_idx = src.find('if tool_call.name == "message_chat":')
        assert shell_idx > 0
        assert match_idx > 0
        assert chat_idx > 0
        assert chat_idx < shell_idx < match_idx, (
            "dispatch reject branches out of order: message_chat should "
            "come first, then the shell branch, then match_glob/match_grep, "
            "then the generic fallback."
        )
