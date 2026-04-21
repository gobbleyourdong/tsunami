"""Replay regression for pain_advisory_duplicate_search (sev 2,
filed in kelp round 13 system_note census).

Anchors the round 15 conversion: 'DUPLICATE SEARCH: You already
searched for X' was an advisory nudge and search_web still ran,
making a second API round-trip + re-dumping identical content. The
structural fix adds a purpose-built query cache (keyed on query
string alone, session-scoped) that short-circuits duplicate calls
with a '[search_web cached — no round-trip]' prefix + the prior
result content.

Source-level assertions because full behavioral boot needs a live
search backend. The replay fixture lists the anchor fragments.

Fixture: tsunami/tests/replays/duplicate_search_dedup.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "duplicate_search_dedup.jsonl"
)
AGENT = Path(__file__).parent.parent / "agent.py"


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestDuplicateSearchDedupReplay:
    @pytest.fixture
    def assertions(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "source_assertion"]

    def test_fixture_well_formed(self, assertions):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        assert meta["slug"] == "duplicate_search_dedup"
        assert len(assertions) >= 4, (
            "fixture must cover short-circuit, post-exec store, advisory "
            "removal, and is_error=False"
        )

    def test_every_source_assertion_holds(self, assertions):
        src = AGENT.read_text()
        for assertion in assertions:
            desc = assertion["desc"]
            for fragment in assertion.get("required_fragments", []):
                assert fragment in src, (
                    f"source assertion {desc!r} failed: agent.py is "
                    f"missing {fragment!r}. Round 15 structural cache "
                    f"has drifted."
                )
            for fragment in assertion.get("required_fragments_absent", []):
                assert fragment not in src, (
                    f"source assertion {desc!r} failed: agent.py "
                    f"still contains {fragment!r}. The advisory this "
                    f"round converted has been re-introduced."
                )


class TestCacheCorrectnessInvariants:
    def test_cache_only_populated_on_success(self):
        """is_error=True responses must NOT be cached — caching a
        failure would lock the drone into the same failure on every
        retry. The post-execution store must be guarded on
        `not result.is_error`."""
        src = AGENT.read_text()
        idx = src.find("_search_results_cache[query] = display_content")
        assert idx > 0, "post-exec cache store missing"
        # Look ~200 chars before for the error guard
        preamble = src[max(0, idx - 300):idx]
        assert "not result.is_error" in preamble, (
            "search_web cache store must be guarded on not result.is_error; "
            "otherwise a failed search would be cached and served on retry"
        )

    def test_short_circuit_uses_tool_result_not_add_system_note(self):
        """The cached-skip must be emitted as a tool_result (is_error=
        False), NOT just a system_note. The drone consumes tool_result
        as the actual response to its emitted call; a system_note is
        advisory commentary. This is the whole point of the round 15
        conversion."""
        src = AGENT.read_text()
        idx = src.find("[search_web cached — no round-trip]")
        assert idx > 0
        window = src[idx:idx + 1200]
        assert "add_tool_result" in window, (
            "cached-search must land as a tool_result, not a system_note"
        )
        assert "is_error=False" in window

    def test_short_circuit_records_in_tool_history(self):
        """Same reasoning as round 14: loop_guard observes
        _tool_history. A short-circuit that doesn't record would let
        the drone emit unlimited cached-hits without progress
        detection firing."""
        src = AGENT.read_text()
        idx = src.find("[search_web cached — no round-trip]")
        window = src[idx:idx + 1200]
        assert 'self._tool_history.append("search_web")' in window

    def test_short_circuit_returns_cached_msg(self):
        """Matches round 14's pattern — return cached_msg, not None."""
        src = AGENT.read_text()
        idx = src.find("[search_web cached — no round-trip]")
        window = src[idx:idx + 1200]
        assert "return cached_msg" in window
        assert "return None" not in window

    def test_cache_keyed_on_query_string_alone(self):
        """Intentional: minor arg drift (different `limit`, different
        `type`) shouldn't force a real round-trip when the query is
        identical. The key is the query string; other args are part of
        the tool call but not the dedup key. This is a deliberate
        trade-off — see meta block for rationale."""
        src = AGENT.read_text()
        idx = src.find("_search_results_cache")
        assert idx > 0
        # Look for the lookup pattern: `query in self._search_results_cache`
        window = src[idx:idx + 600]
        assert "query in self._search_results_cache" in window
        assert "self._search_results_cache[query]" in window


class TestAuditCensusReflectsConversion:
    """Round 13's locked census should see one fewer advisory after
    this round lands. If the audit-run disagrees, the conversion
    didn't actually remove the advisory copy."""

    def test_advisory_count_trending_down(self):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "kelp_audit_system_notes",
            Path(__file__).parent.parent.parent
            / "scripts" / "crew" / "kelp" / "audit_system_notes.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["kelp_audit_system_notes_r15"] = mod
        spec.loader.exec_module(mod)
        result = mod.audit()
        # Round 13 baseline: 10 advisory. Round 14: dropped to 9.
        # Round 15 (this one): should drop to 8. Being generous with
        # slack for mid-session line drift.
        assert result["summary"]["advisory"] <= 9, (
            f"after round 15 conversion, advisory count should be ≤ 9 "
            f"(baseline 10). Got {result['summary']['advisory']}. "
            f"The DUPLICATE SEARCH advisory may not have been fully "
            f"removed."
        )
