"""Replay regression for pain_message_chat_pattern_hallucination (severity 4).

Anchors the dispatch-layer rewrite at
`tsunami.tools.rewrite_message_chat_pattern_hallucination`. The drone
(Qwen3.6-35B) emits `message_chat` in phases where only `message_result`
is allowed — sigma v8 M8 failure mode #2 (pattern hallucination from
adjacent precedents). Rather than reject with a prompt-level error that
the drone ignores, the rewrite converts `message_chat(text, done=true)`
to `message_result(text=...)` structurally.

Trace sources: 4 sessions on 2026-04-20 (1776734971 / 1776735292 /
1776736683 / 1776737677). The dispatch already rejected these at the
schema filter; the rewrite catches the intent before the reject fires,
saving the iteration that would otherwise be wasted.

Fixture: tsunami/tests/replays/message_chat_pattern_hallucination.jsonl
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from tsunami.tools import rewrite_message_chat_pattern_hallucination


REPLAY_PATH = (
    Path(__file__).parent / "replays"
    / "message_chat_pattern_hallucination.jsonl"
)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _make_tool_call(input_spec: dict):
    """Shape matching the agent.py dispatch site: tool_call has .name
    (str) and .arguments (dict) and is mutable — SimpleNamespace fits."""
    return SimpleNamespace(
        name=input_spec["name"],
        arguments=dict(input_spec.get("arguments", {})),
    )


class TestMessageChatRewriteReplay:
    """Replay every case from the fixture; each asserts the rewrite
    decision matches the recorded expect block."""

    @pytest.fixture
    def events(self):
        return _load_replay(REPLAY_PATH)

    def test_fixture_well_formed(self, events):
        meta = next(e for e in events if e["kind"] == "meta")
        cases = [e for e in events if e["kind"] == "rewrite_case"]
        assert meta["slug"] == "message_chat_pattern_hallucination"
        assert len(cases) >= 6, \
            "fixture must cover canonical + negative + edge cases"

    def test_every_case_matches_expect(self, events, caplog):
        cases = [e for e in events if e["kind"] == "rewrite_case"]
        log = logging.getLogger("tsunami.agent")
        for case in cases:
            tool_call = _make_tool_call(case["input"])
            allowed = set(case["allowed"])
            with caplog.at_level(logging.WARNING, logger="tsunami.agent"):
                rewrote = rewrite_message_chat_pattern_hallucination(
                    tool_call, allowed, case["phase"], log,
                )
            expect = case["expect"]
            assert rewrote == expect["rewritten"], (
                f"case {case['desc']!r}: expected rewritten={expect['rewritten']}, "
                f"got {rewrote}. tool_call={tool_call!r}"
            )
            if expect["rewritten"]:
                assert tool_call.name == expect["final_name"], (
                    f"case {case['desc']!r}: final name mismatch. "
                    f"got {tool_call.name!r}, expected {expect['final_name']!r}"
                )
                assert tool_call.arguments.get("text") == expect["final_args_text"], (
                    f"case {case['desc']!r}: text preservation failed. "
                    f"got {tool_call.arguments.get('text')!r}"
                )
            else:
                # Non-rewrites must leave the tool_call untouched
                original = case["input"]
                assert tool_call.name == original["name"]
                assert tool_call.arguments == dict(original.get("arguments", {})), (
                    f"case {case['desc']!r}: arguments mutated on non-rewrite path"
                )


class TestRewriteHelperBoundaries:
    """Direct boundary tests on the helper — cover cases the replay
    fixture doesn't make vivid."""

    def _mk(self, name, **args):
        return SimpleNamespace(name=name, arguments=args)

    def test_no_mutation_on_false_return(self):
        tc = self._mk("file_write", path="src/App.tsx", content="x")
        allowed = {"file_write", "message_result"}
        rewrote = rewrite_message_chat_pattern_hallucination(
            tc, allowed, "WRITE", None,
        )
        assert rewrote is False
        assert tc.name == "file_write"
        assert tc.arguments == {"path": "src/App.tsx", "content": "x"}

    def test_accepts_none_logger(self):
        """Helper must work when log_ is None (defensive callers,
        tests that don't want to capture warnings)."""
        tc = self._mk("message_chat", text="ok", done=True)
        allowed = {"message_result"}
        assert rewrite_message_chat_pattern_hallucination(
            tc, allowed, "WRITE", None,
        ) is True
        assert tc.name == "message_result"

    def test_done_various_truthy_strings(self):
        """Training data sometimes stringifies booleans; helper accepts
        'True', 'true', True, and unset as final-intent."""
        for done_val in (True, "true", "True", "TRUE"):
            tc = self._mk("message_chat", text="t", done=done_val)
            allowed = {"message_result"}
            assert rewrite_message_chat_pattern_hallucination(
                tc, allowed, "WRITE", None,
            ) is True, f"done={done_val!r} should trigger rewrite"
            assert tc.name == "message_result"

    def test_done_various_falsy_blocks_rewrite(self):
        for done_val in (False, "false", "False", 0):
            tc = self._mk("message_chat", text="wip", done=done_val)
            allowed = {"message_result"}
            # Note: the helper interprets `done_val is True or str(...)=='true'`.
            # 0/False/'false' all fail both branches → rewrite skipped.
            assert rewrite_message_chat_pattern_hallucination(
                tc, allowed, "WRITE", None,
            ) is False, f"done={done_val!r} should NOT trigger rewrite"
            assert tc.name == "message_chat"

    def test_empty_arguments_dict(self):
        """Drone may emit message_chat with zero args — still rewrites
        to message_result(text='') because the default done is True."""
        tc = self._mk("message_chat")
        allowed = {"message_result"}
        assert rewrite_message_chat_pattern_hallucination(
            tc, allowed, "DELIVER", None,
        ) is True
        assert tc.name == "message_result"
        assert tc.arguments.get("text") == ""

    def test_none_arguments(self):
        """Defensive: tool_call.arguments can be None in some extractor
        paths. Helper guards with `args or {}` so it never crashes —
        and since empty args default to done=True, it proceeds with
        the rewrite as the canonical case."""
        tc = SimpleNamespace(name="message_chat", arguments=None)
        allowed = {"message_result"}
        assert rewrite_message_chat_pattern_hallucination(
            tc, allowed, "WRITE", None,
        ) is True
        assert tc.name == "message_result"
        assert tc.arguments.get("text") == ""

    def test_message_chat_allowed_via_qa_toolbox_preserved(self):
        """DELIVER/POLISH legitimately expose message_chat. Must not rewrite."""
        tc = self._mk("message_chat", text="polish done", done=True)
        allowed = {"message_chat", "message_result", "undertow"}
        assert rewrite_message_chat_pattern_hallucination(
            tc, allowed, "DELIVER", None,
        ) is False
        assert tc.name == "message_chat"

    def test_no_message_result_available_blocks_rewrite(self):
        """If message_result also isn't in the allowed set, rewriting
        would just shift the failure. Helper must leave it alone."""
        tc = self._mk("message_chat", text="x", done=True)
        allowed = {"file_write"}  # tiny forced phase
        assert rewrite_message_chat_pattern_hallucination(
            tc, allowed, "SCAFFOLD", None,
        ) is False


class TestDispatchIntegration:
    """Source-level assertion that agent.py wires the helper into the
    dispatch path at the correct site (before the schema-filter reject).
    A future refactor that drops the helper call would fail here loud."""

    def test_agent_calls_rewrite_helper(self):
        src = (Path(__file__).parent.parent / "agent.py").read_text()
        assert "rewrite_message_chat_pattern_hallucination" in src, (
            "agent.py no longer calls rewrite_message_chat_pattern_hallucination "
            "at the dispatch site. The message_chat → message_result rewrite "
            "is load-bearing; drones will re-spiral on pattern-hallucinated "
            "message_chat calls without it."
        )

    def test_reject_path_names_message_result(self):
        """Even when the helper doesn't rewrite (done=false), the reject
        error must point the drone at the right next step. If the
        special-cased reject message disappears, pattern hallucination
        will keep wasting iterations."""
        src = (Path(__file__).parent.parent / "agent.py").read_text()
        assert "If you're done, use message_result" in src, (
            "agent.py lost the tailored message_chat reject helper that "
            "names message_result as the next step. Restore the branch."
        )
