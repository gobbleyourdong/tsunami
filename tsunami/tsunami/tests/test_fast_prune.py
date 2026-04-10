"""Tests for fast_prune with TOOL_RESULT_CLEARED_MESSAGE ."""

import pytest

from tsunami.state import AgentState, Message
from tsunami.compression import fast_prune, estimate_tokens
from tsunami.tool_result_storage import TOOL_RESULT_CLEARED_MESSAGE


class TestFastPrune:
    """fast_prune replaces verbose tool results with cleared message."""

    def _build_state(self, n_tool_results: int, content_size: int = 1000) -> AgentState:
        """Build a state with system + user + N tool results."""
        state = AgentState()
        state.add_system("You are an agent.")
        state.add_user("Do something.")
        for i in range(n_tool_results):
            state.conversation.append(Message(
                role="tool_result",
                content=f"[shell_exec] {'x' * content_size}",
            ))
        # Add a few recent messages that should be kept
        state.conversation.append(Message(role="assistant", content="thinking..."))
        state.conversation.append(Message(role="tool_result", content="[file_read] recent result"))
        return state

    def test_prunes_verbose_results(self):
        state = self._build_state(10, content_size=2000)
        before = estimate_tokens(state)
        freed = fast_prune(state, keep_recent=2)
        assert freed > 0
        after = estimate_tokens(state)
        assert after < before

    def test_uses_cleared_message(self):
        state = self._build_state(5, content_size=2000)
        fast_prune(state, keep_recent=2)
        # Check that pruned messages use the cleared message
        pruned = [m for m in state.conversation if TOOL_RESULT_CLEARED_MESSAGE in m.content]
        assert len(pruned) > 0

    def test_preserves_recent(self):
        state = self._build_state(10, content_size=2000)
        fast_prune(state, keep_recent=2)
        # Last 2 messages should be untouched
        assert "recent result" in state.conversation[-1].content

    def test_preserves_errors(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        state.conversation.append(Message(
            role="tool_result",
            content="[shell_exec] ERROR: command not found " + "x" * 2000,
        ))
        state.conversation.append(Message(role="assistant", content="ok"))
        fast_prune(state, keep_recent=1)
        # Error messages should be kept (not pruned)
        error_msgs = [m for m in state.conversation if "ERROR" in m.content]
        assert len(error_msgs) >= 1

    def test_preserves_short_results(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        state.conversation.append(Message(
            role="tool_result",
            content="[file_write] Wrote 5 lines to test.py",
        ))
        state.conversation.append(Message(role="assistant", content="done"))
        fast_prune(state, keep_recent=1)
        # Short results (< 500 chars) should survive
        short = [m for m in state.conversation if "Wrote 5 lines" in m.content]
        assert len(short) == 1

    def test_preserves_persisted_filepath(self):
        """When pruning a persisted result, the filepath reference survives."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        state.conversation.append(Message(
            role="tool_result",
            content=(
                "[200 lines (48.8 KB) -> .context/abc123def456.txt]\n"
                + "x\n" * 200
            ),
        ))
        state.conversation.append(Message(role="assistant", content="recent"))
        fast_prune(state, keep_recent=1)
        # The .context/ reference should survive pruning
        pruned = [m for m in state.conversation if ".context/" in m.content]
        assert len(pruned) == 1

    def test_not_enough_messages_to_prune(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        state.conversation.append(Message(role="tool_result", content="short"))
        freed = fast_prune(state, keep_recent=8)
        assert freed == 0
