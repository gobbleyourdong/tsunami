"""Replay regression for pain_advisory_already_in_context_nudge
(sev 3, filed in kelp round 13 system_note census).

Anchors the round 14 conversion: 'You already have X in context from
an earlier file_read' was an advisory nudge — the note fired but the
actual file_read ran anyway, so the drone saw the nudge AND the full
re-dump of the file content. That training signal ('the nudge doesn't
matter — I still get the file') pushed the drone toward ignoring the
note. The structural fix short-circuits the dispatch.

Full behavioral boot of Agent._step would need a live model + tool
registry. Instead these tests assert on agent.py source-level shape —
the required fragments must survive a refactor. The replay fixture
lists them as reject-on-absence anchors.

Fixture: tsunami/tests/replays/already_in_context_dedup.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "already_in_context_dedup.jsonl"
)
AGENT = Path(__file__).parent.parent / "agent.py"


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestAlreadyInContextDedupReplay:
    @pytest.fixture
    def assertions(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "source_assertion"]

    def test_fixture_well_formed(self, assertions):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        assert meta["slug"] == "already_in_context_dedup"
        assert len(assertions) >= 4, (
            "fixture must cover the short-circuit block, path aliasing, "
            "cache invalidation, tool_history bookkeeping, and advisory "
            "removal"
        )

    def test_every_source_assertion_holds(self, assertions):
        src = AGENT.read_text()
        for assertion in assertions:
            desc = assertion["desc"]
            for fragment in assertion.get("required_fragments", []):
                assert fragment in src, (
                    f"source assertion {desc!r} failed: agent.py is "
                    f"missing {fragment!r}. Round 14's structural "
                    f"conversion has drifted."
                )
            for fragment in assertion.get("required_fragments_absent", []):
                assert fragment not in src, (
                    f"source assertion {desc!r} failed: agent.py "
                    f"still contains {fragment!r}. The advisory that "
                    f"this round converted has been re-introduced."
                )


class TestDedupBehaviorInvariants:
    """Properties the fix must uphold across edits."""

    def test_cache_is_invalidated_on_file_write(self):
        """The fix keeps the existing invalidation branch — without it,
        a re-read after a legitimate file_write would short-circuit
        incorrectly and the drone would see stale content."""
        src = AGENT.read_text()
        # The invalidation pattern: file_write/file_edit branch
        # discards the edited path from _files_already_read.
        assert 'if tool_call.name in ("file_write", "file_edit"):' in src
        assert "_files_already_read.discard(edit_path)" in src

    def test_short_circuit_is_not_an_error(self):
        """Cached-skip uses is_error=False. An error code would
        trigger error-retry backoff in loop_guard, which is wrong:
        skipping a redundant read is success, not failure."""
        src = AGENT.read_text()
        # Locate the cached-skip block and check is_error=False near it.
        idx = src.find("[file_read cached — skipped]")
        assert idx > 0, "cached-skip block missing"
        window = src[idx:idx + 1500]
        assert "is_error=False" in window, (
            "cached-skip must emit is_error=False so the skip isn't "
            "misread as an error in loop_guard / retry paths"
        )

    def test_short_circuit_returns_cached_msg_from_step(self):
        """_step's return type is str — the cached-skip path must
        return a string, not None (would trip the int/str return
        annotation and downstream callers)."""
        src = AGENT.read_text()
        idx = src.find("[file_read cached — skipped]")
        assert idx > 0
        window = src[idx:idx + 1500]
        assert "return cached_msg" in window
        assert "return None" not in window, (
            "cached-skip must return the message string, not None"
        )

    def test_path_alias_coalesces_qwen_canonical(self):
        """Without coalescing, the drone could sneak a second read
        past the cache by emitting `file_path=` instead of `path=`
        — the underlying tool accepts both aliases, and the dedup
        lookup must match that surface."""
        src = AGENT.read_text()
        idx = src.find("_files_already_read:")
        assert idx > 0
        # Look for the lookup site (not the set init):
        idx2 = src.find("_files_already_read", idx + 20)
        assert idx2 > 0
        # The read-branch coalesces arguments in a single get chain.
        assert 'tool_call.arguments.get("path")' in src
        assert 'tool_call.arguments.get("file_path")' in src

    def test_tool_history_appends_skipped_read(self):
        """The short-circuit records `file_read` in _tool_history so
        loop_guard treats the skip as a distinct attempt. Without
        this, the drone could get free repeated skip attempts without
        loop_guard seeing progress at all."""
        src = AGENT.read_text()
        idx = src.find("[file_read cached — skipped]")
        assert idx > 0
        window = src[idx:idx + 1500]
        assert 'self._tool_history.append("file_read")' in window
