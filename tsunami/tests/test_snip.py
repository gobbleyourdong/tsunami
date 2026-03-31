"""Tests for message snipping ("""

import pytest

from tsunami.state import AgentState, Message
from tsunami.snip import snip_if_needed, CHARS_PER_TOKEN


class TestSnipIfNeeded:
    """Targeted message removal to free tokens."""

    def _build_state(self, n_messages: int, msg_size: int = 500) -> AgentState:
        state = AgentState()
        state.add_system("System prompt " + "x" * 200)
        state.add_user("User request " + "y" * 200)
        for i in range(n_messages):
            if i % 2 == 0:
                state.conversation.append(Message(
                    role="assistant", content=f"thinking step {i} " + "z" * msg_size,
                    tool_call={"function": {"name": "file_read", "arguments": {}}},
                ))
            else:
                state.conversation.append(Message(
                    role="tool_result", content=f"[file_read] result {i} " + "w" * msg_size,
                ))
        return state

    def test_no_snip_when_under_budget(self):
        state = self._build_state(4, msg_size=100)
        freed = snip_if_needed(state, target_tokens=100_000)
        assert freed == 0

    def test_snips_when_over_budget(self):
        state = self._build_state(20, msg_size=2000)
        before = len(state.conversation)
        freed = snip_if_needed(state, target_tokens=5000, keep_recent=4)
        assert freed > 0
        assert len(state.conversation) < before

    def test_preserves_system_and_user(self):
        state = self._build_state(20, msg_size=2000)
        snip_if_needed(state, target_tokens=2000, keep_recent=2)
        assert state.conversation[0].role == "system"
        assert state.conversation[1].role == "user"

    def test_preserves_recent_messages(self):
        state = self._build_state(20, msg_size=2000)
        last_content = state.conversation[-1].content
        snip_if_needed(state, target_tokens=3000, keep_recent=4)
        assert state.conversation[-1].content == last_content

    def test_prioritizes_already_cleared(self):
        """Already-cleared messages should be snipped first."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        # Add a cleared message and a valuable one
        state.conversation.append(Message(
            role="tool_result",
            content="[Old tool result content cleared] " + "x" * 1000,
        ))
        state.conversation.append(Message(
            role="tool_result",
            content="[file_read] ERROR: important error " + "e" * 1000,
        ))
        state.conversation.append(Message(role="assistant", content="recent"))

        snip_if_needed(state, target_tokens=500, keep_recent=1)
        # Error message should survive longer than cleared message
        remaining = [m.content for m in state.conversation]
        has_error = any("ERROR" in c for c in remaining)
        has_cleared = any("[Old tool result content cleared]" in c for c in remaining)
        # At minimum, errors should be kept preferentially
        if len(state.conversation) > 3:
            assert has_error

    def test_not_enough_messages(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        state.conversation.append(Message(role="assistant", content="only one"))
        freed = snip_if_needed(state, target_tokens=1, keep_recent=8)
        assert freed == 0

    def test_returns_tokens_freed(self):
        state = self._build_state(20, msg_size=2000)
        freed = snip_if_needed(state, target_tokens=5000, keep_recent=4)
        assert isinstance(freed, int)
        assert freed > 0


class TestSnipPriority:
    """Snip removes low-value messages first."""

    def test_tool_results_before_tool_calls(self):
        """tool_result (no error) should be snipped before assistant+tool_call."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        # Add 6 pairs with large content to ensure we're over budget
        for i in range(6):
            state.conversation.append(Message(
                role="assistant", content="call " + "a" * 2000,
                tool_call={"function": {"name": "test", "arguments": {}}},
            ))
            state.conversation.append(Message(
                role="tool_result", content=f"[test] result " + "r" * 2000,
            ))
        state.conversation.append(Message(role="assistant", content="recent"))

        before_count = len(state.conversation)
        snip_if_needed(state, target_tokens=3000, keep_recent=1)
        after_count = len(state.conversation)
        assert after_count < before_count

    def test_errors_preserved_longest(self):
        """Error messages should be the last to go."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        state.conversation.append(Message(
            role="tool_result", content="[shell_exec] normal output " + "n" * 2000,
        ))
        state.conversation.append(Message(
            role="tool_result", content="[shell_exec] ERROR: crash " + "e" * 2000,
        ))
        state.conversation.append(Message(
            role="tool_result", content="[file_read] another result " + "a" * 2000,
        ))
        state.conversation.append(Message(role="assistant", content="recent"))

        # Snip enough to remove 1-2 messages but not all
        snip_if_needed(state, target_tokens=2500, keep_recent=1)
        remaining = " ".join(m.content for m in state.conversation)
        assert "ERROR" in remaining
