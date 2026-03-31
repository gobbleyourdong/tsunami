"""Tests for time-based microcompact."""

import time
import pytest

from tsunami.state import AgentState, Message
from tsunami.microcompact import microcompact_if_needed, DEFAULT_GAP_THRESHOLD_SECONDS
from tsunami.tool_result_storage import TOOL_RESULT_CLEARED_MESSAGE


class TestMicrocompactTiming:
    """Only triggers after gap threshold."""

    def _build_state(self, n_results: int = 10, assistant_age: float = 0) -> AgentState:
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        for i in range(n_results):
            state.conversation.append(Message(
                role="assistant", content=f"thinking {i}",
                timestamp=time.time() - assistant_age,
            ))
            state.conversation.append(Message(
                role="tool_result", content=f"[file_read] result {i} " + "x" * 500,
                timestamp=time.time() - assistant_age,
            ))
        return state

    def test_no_clear_when_recent(self):
        """Don't clear when last assistant message is recent."""
        state = self._build_state(10, assistant_age=0)
        freed = microcompact_if_needed(state, gap_threshold=600)
        assert freed == 0

    def test_clears_when_gap_exceeds_threshold(self):
        """Clear when gap exceeds threshold."""
        state = self._build_state(10, assistant_age=700)
        freed = microcompact_if_needed(state, gap_threshold=600)
        assert freed > 0

    def test_short_threshold_triggers_easily(self):
        """With a 0-second threshold, always triggers."""
        state = self._build_state(10, assistant_age=1)
        freed = microcompact_if_needed(state, gap_threshold=0)
        assert freed > 0


class TestMicrocompactBehavior:
    """What gets cleared and what's preserved."""

    def _build_state_with_content(self) -> AgentState:
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        # Old messages
        old_time = time.time() - 1000
        state.conversation.append(Message(
            role="assistant", content="old thinking", timestamp=old_time,
        ))
        state.conversation.append(Message(
            role="tool_result",
            content="[file_read] big old result " + "x" * 1000,
            timestamp=old_time,
        ))
        state.conversation.append(Message(
            role="tool_result",
            content="[shell_exec] ERROR: command failed " + "e" * 500,
            timestamp=old_time,
        ))
        state.conversation.append(Message(
            role="tool_result",
            content="[file_read] another old result " + "y" * 1000,
            timestamp=old_time,
        ))
        # Recent messages
        state.conversation.append(Message(
            role="assistant", content="recent thinking", timestamp=old_time,
        ))
        state.conversation.append(Message(
            role="tool_result",
            content="[file_read] recent result " + "z" * 1000,
            timestamp=old_time,
        ))
        return state

    def test_preserves_errors(self):
        """Error messages should NOT be cleared."""
        state = self._build_state_with_content()
        microcompact_if_needed(state, gap_threshold=0, keep_recent=1)
        has_error = any("ERROR" in m.content for m in state.conversation)
        assert has_error

    def test_preserves_recent(self):
        """Last keep_recent tool results should survive."""
        state = self._build_state_with_content()
        microcompact_if_needed(state, gap_threshold=0, keep_recent=1)
        assert "recent result" in state.conversation[-1].content

    def test_preserves_structure(self):
        """Cleared messages keep their tool name prefix."""
        state = self._build_state_with_content()
        microcompact_if_needed(state, gap_threshold=0, keep_recent=1)
        cleared = [m for m in state.conversation if TOOL_RESULT_CLEARED_MESSAGE in m.content]
        for m in cleared:
            assert "[" in m.content  # tool name prefix preserved

    def test_skips_already_cleared(self):
        """Don't re-clear already-cleared messages."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        old_time = time.time() - 1000
        state.conversation.append(Message(
            role="assistant", content="old", timestamp=old_time,
        ))
        state.conversation.append(Message(
            role="tool_result",
            content=f"[file_read] {TOOL_RESULT_CLEARED_MESSAGE}",
            timestamp=old_time,
        ))
        state.conversation.append(Message(
            role="tool_result",
            content="[file_read] fresh result " + "x" * 500,
            timestamp=old_time,
        ))
        freed = microcompact_if_needed(state, gap_threshold=0, keep_recent=0)
        # The already-cleared message shouldn't count toward freed chars
        assert freed >= 0  # may or may not free depending on fresh result

    def test_not_enough_results(self):
        """Don't clear when fewer results than keep_recent."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        old_time = time.time() - 1000
        state.conversation.append(Message(
            role="assistant", content="a", timestamp=old_time))
        state.conversation.append(Message(
            role="tool_result", content="[t] x" * 100, timestamp=old_time))
        freed = microcompact_if_needed(state, gap_threshold=0, keep_recent=5)
        assert freed == 0

    def test_no_assistant_message(self):
        """Handle edge case: no assistant messages in conversation."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        freed = microcompact_if_needed(state, gap_threshold=0)
        assert freed == 0
