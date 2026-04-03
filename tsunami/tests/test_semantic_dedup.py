"""Tests for Chunk 3: Semantic Deduplication.

Verifies:
- Content-identical messages deduplicated (keep newest)
- Repeated errors collapsed to count
- Same-path file_read kept only latest
- Integration with fast_prune pipeline
- Short messages not affected
- Recent messages protected
"""

from tsunami.semantic_dedup import (
    dedup_messages,
    _content_hash,
    _extract_file_path,
    _extract_error_key,
    HASH_PREFIX_LEN,
    MIN_DEDUP_LEN,
)
from tsunami.state import AgentState, Message
from tsunami.tool_result_storage import TOOL_RESULT_CLEARED_MESSAGE


def _build_state(messages):
    """Build an AgentState with system + user + given messages."""
    state = AgentState()
    state.add_system("system prompt")
    state.add_user("build something")
    for m in messages:
        state.conversation.append(m)
    return state


class TestContentDedup:
    """Identical content messages — keep newest."""

    def test_two_identical_keeps_newest(self):
        content = "x" * 300  # over MIN_DEDUP_LEN
        state = _build_state([
            Message(role="tool_result", content=content, timestamp=1.0),
            Message(role="assistant", content="ack"),
            Message(role="tool_result", content=content, timestamp=2.0),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        assert freed > 0
        # First occurrence should be cleared
        assert TOOL_RESULT_CLEARED_MESSAGE in state.conversation[2].content
        # Second (newer) should survive
        assert state.conversation[4].content == content

    def test_three_identical_keeps_newest(self):
        content = "verbose output\n" * 30
        state = _build_state([
            Message(role="tool_result", content=content),
            Message(role="assistant", content="a"),
            Message(role="tool_result", content=content),
            Message(role="assistant", content="b"),
            Message(role="tool_result", content=content),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        assert freed > 0
        # First two should be cleared
        cleared = [m for m in state.conversation if TOOL_RESULT_CLEARED_MESSAGE in m.content]
        assert len(cleared) == 2

    def test_different_content_untouched(self):
        state = _build_state([
            Message(role="tool_result", content="a" * 300),
            Message(role="assistant", content="x"),
            Message(role="tool_result", content="b" * 300),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        assert freed == 0

    def test_short_messages_not_deduped(self):
        content = "short"
        state = _build_state([
            Message(role="tool_result", content=content),
            Message(role="assistant", content="x"),
            Message(role="tool_result", content=content),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        assert freed == 0


class TestErrorCollapse:
    """Repeated errors collapsed to count."""

    def test_repeated_errors_collapsed(self):
        error = "[shell_exec] ERROR: Cannot find module './App'\n" + "x" * 200
        state = _build_state([
            Message(role="tool_result", content=error),
            Message(role="assistant", content="try fix"),
            Message(role="tool_result", content=error),
            Message(role="assistant", content="try again"),
            Message(role="tool_result", content=error),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        assert freed > 0
        # Newest should have count annotation
        surviving = [m for m in state.conversation
                     if m.role == "tool_result" and "ERROR" in m.content
                     and TOOL_RESULT_CLEARED_MESSAGE not in m.content]
        assert len(surviving) == 1
        assert "3x" in surviving[0].content

    def test_single_error_not_collapsed(self):
        error = "[shell_exec] ERROR: Something broke\n" + "x" * 200
        state = _build_state([
            Message(role="tool_result", content=error),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        # No dedup should happen
        assert "occurred" not in state.conversation[2].content

    def test_different_errors_not_collapsed(self):
        err1 = "[shell_exec] ERROR: Module not found\n" + "a" * 200
        err2 = "[shell_exec] ERROR: Syntax error in App.tsx\n" + "b" * 200
        state = _build_state([
            Message(role="tool_result", content=err1),
            Message(role="assistant", content="x"),
            Message(role="tool_result", content=err2),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        # Both should survive (different errors)
        errors = [m for m in state.conversation
                  if m.role == "tool_result" and "ERROR" in m.content
                  and TOOL_RESULT_CLEARED_MESSAGE not in m.content]
        assert len(errors) == 2


class TestFileReadDedup:
    """Same-path file_read — keep only latest."""

    def test_same_path_keeps_latest(self):
        read1 = "[file_read] src/App.tsx\nconst old = true;\n" + "x" * 200
        read2 = "[file_read] src/App.tsx\nconst new_ = true;\n" + "y" * 200
        state = _build_state([
            Message(role="tool_result", content=read1),
            Message(role="assistant", content="editing"),
            Message(role="tool_result", content=read2),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        assert freed > 0
        # First read should be cleared, second survives
        assert "superseded" in state.conversation[2].content or TOOL_RESULT_CLEARED_MESSAGE in state.conversation[2].content

    def test_different_paths_both_kept(self):
        read1 = "[file_read] src/App.tsx\n" + "x" * 200
        read2 = "[file_read] src/types.ts\n" + "y" * 200
        state = _build_state([
            Message(role="tool_result", content=read1),
            Message(role="assistant", content="x"),
            Message(role="tool_result", content=read2),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        # Content is different so no content dedup, paths different so no path dedup
        cleared = [m for m in state.conversation if "superseded" in m.content]
        assert len(cleared) == 0


class TestKeepRecent:
    """Recent messages are protected from dedup."""

    def test_recent_messages_untouched(self):
        content = "x" * 300
        state = _build_state([
            Message(role="tool_result", content=content),
            Message(role="tool_result", content=content),
        ])
        # keep_recent=5 means both messages are in the "recent" zone
        freed = dedup_messages(state, keep_recent=5)
        assert freed == 0

    def test_not_enough_messages(self):
        state = _build_state([
            Message(role="tool_result", content="x" * 300),
        ])
        freed = dedup_messages(state, keep_recent=8)
        assert freed == 0


class TestHelpers:
    """Helper function tests."""

    def test_content_hash_deterministic(self):
        assert _content_hash("hello world") == _content_hash("hello world")

    def test_content_hash_different(self):
        assert _content_hash("hello") != _content_hash("world")

    def test_content_hash_uses_prefix(self):
        # Same first 200 chars → same hash
        base = "x" * 200
        assert _content_hash(base + "aaa") == _content_hash(base + "bbb")

    def test_extract_file_path_standard(self):
        assert _extract_file_path("[file_read] src/App.tsx\ncontent") == "src/App.tsx"

    def test_extract_file_path_with_parens(self):
        assert _extract_file_path("[file_read] src/App.tsx (200 lines)") == "src/App.tsx"

    def test_extract_file_path_none(self):
        assert _extract_file_path("no file path here") is None

    def test_extract_error_key_found(self):
        key = _extract_error_key("[shell_exec] ERROR: Module not found './App'")
        assert key is not None
        assert "Module not found" in key

    def test_extract_error_key_strips_timestamps(self):
        key = _extract_error_key("2026-04-03T18:00:00 ERROR: Something broke")
        assert key is not None
        assert "2026" not in key

    def test_extract_error_key_normalizes_line_numbers(self):
        k1 = _extract_error_key("ERROR at line 42: syntax error")
        k2 = _extract_error_key("ERROR at line 99: syntax error")
        assert k1 == k2  # same error, different line

    def test_extract_error_key_none(self):
        assert _extract_error_key("everything is fine") is None


class TestTokenSavings:
    """Verify real token savings from dedup."""

    def test_10_identical_errors_massive_savings(self):
        """The PLAN.md test: 10 identical errors should collapse to 1."""
        error = "[shell_exec] ERROR: Cannot find module './components/Chart'\n" + "stack trace\n" * 20
        messages = []
        for _ in range(10):
            messages.append(Message(role="tool_result", content=error))
            messages.append(Message(role="assistant", content="let me try again"))

        state = _build_state(messages)
        freed = dedup_messages(state, keep_recent=1)
        assert freed > 0

        # Only 1 error should survive with a count
        surviving_errors = [m for m in state.conversation
                            if "ERROR" in m.content
                            and TOOL_RESULT_CLEARED_MESSAGE not in m.content]
        assert len(surviving_errors) == 1
        assert "10x" in surviving_errors[0].content

    def test_mixed_dedup_scenario(self):
        """Realistic scenario: some dupes, some unique, some errors."""
        file_content = "[file_read] src/App.tsx\n" + "code\n" * 50
        error = "[shell_exec] ERROR: Build failed\n" + "x" * 200
        unique = "[shell_exec] npm install output\n" + "y" * 200

        state = _build_state([
            Message(role="tool_result", content=file_content),
            Message(role="assistant", content="a"),
            Message(role="tool_result", content=error),
            Message(role="assistant", content="b"),
            Message(role="tool_result", content=file_content),  # dupe read
            Message(role="assistant", content="c"),
            Message(role="tool_result", content=error),  # dupe error
            Message(role="assistant", content="d"),
            Message(role="tool_result", content=unique),
            Message(role="assistant", content="recent"),
        ])
        freed = dedup_messages(state, keep_recent=1)
        assert freed > 0
        # unique should survive
        assert any(m.content == unique for m in state.conversation)
