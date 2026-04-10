"""Tests for context analysis — token usage breakdown and suggestions."""

import pytest

from tsunami.state import AgentState, Message
from tsunami.context_analysis import (
    analyze_context,
    ContextAnalysis,
    ToolUsageBreakdown,
    _extract_tool_name,
    TOOL_RESULT_BLOAT_THRESHOLD,
)


class TestExtractToolName:
    """Parse tool name from result prefix."""

    def test_standard_prefix(self):
        assert _extract_tool_name("[file_read] contents...") == "file_read"

    def test_shell_exec(self):
        assert _extract_tool_name("[shell_exec] output...") == "shell_exec"

    def test_no_prefix(self):
        assert _extract_tool_name("plain text result") == "unknown"

    def test_error_prefix(self):
        assert _extract_tool_name("[file_read] ERROR: not found") == "file_read"


class TestAnalyzeContext:
    """Full context analysis."""

    def _build_state(self) -> AgentState:
        state = AgentState()
        state.add_system("System prompt " + "x" * 200)
        state.add_user("User request")
        # Simulate a few tool calls
        state.add_assistant("thinking", tool_call={
            "function": {"name": "file_read", "arguments": {"path": "test.py"}},
        })
        state.conversation.append(Message(
            role="tool_result",
            content="[file_read] " + "content " * 500,
        ))
        state.add_assistant("more thinking", tool_call={
            "function": {"name": "shell_exec", "arguments": {"command": "ls"}},
        })
        state.conversation.append(Message(
            role="tool_result",
            content="[shell_exec] " + "output " * 100,
        ))
        return state

    def test_total_tokens_positive(self):
        state = self._build_state()
        analysis = analyze_context(state)
        assert analysis.total_tokens > 0

    def test_system_tokens_counted(self):
        state = self._build_state()
        analysis = analyze_context(state)
        assert analysis.system_tokens > 0

    def test_tool_result_tokens_counted(self):
        state = self._build_state()
        analysis = analyze_context(state)
        assert analysis.tool_result_tokens > 0

    def test_per_tool_breakdown(self):
        state = self._build_state()
        analysis = analyze_context(state)
        assert "file_read" in analysis.tool_usage
        assert "shell_exec" in analysis.tool_usage
        assert analysis.tool_usage["file_read"].call_count == 1
        assert analysis.tool_usage["shell_exec"].call_count == 1

    def test_tool_result_fraction(self):
        state = self._build_state()
        analysis = analyze_context(state)
        assert 0 < analysis.tool_result_fraction < 1

    def test_format_summary(self):
        state = self._build_state()
        analysis = analyze_context(state)
        summary = analysis.format_summary()
        assert "Context:" in summary
        assert "tokens" in summary
        assert "file_read" in summary

    def test_empty_state(self):
        state = AgentState()
        analysis = analyze_context(state)
        assert analysis.total_tokens == 0
        assert analysis.suggestions == []


class TestContextSuggestions:
    """Optimization suggestions based on usage patterns."""

    def test_suggests_on_bloated_file_read(self):
        """Should suggest offset/limit when file_read dominates."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        # Make file_read dominate context
        for _ in range(5):
            state.add_assistant("call", tool_call={
                "function": {"name": "file_read", "arguments": {}},
            })
            state.conversation.append(Message(
                role="tool_result",
                content="[file_read] " + "x" * 5000,
            ))
        analysis = analyze_context(state)
        has_read_suggestion = any("offset" in s.lower() or "limit" in s.lower() for s in analysis.suggestions)
        assert has_read_suggestion

    def test_suggests_on_bloated_shell(self):
        """Should suggest piping when shell_exec dominates."""
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        for _ in range(5):
            state.add_assistant("call", tool_call={
                "function": {"name": "shell_exec", "arguments": {}},
            })
            state.conversation.append(Message(
                role="tool_result",
                content="[shell_exec] " + "output " * 2000,
            ))
        analysis = analyze_context(state)
        has_shell_suggestion = any("pipe" in s.lower() or "head" in s.lower() for s in analysis.suggestions)
        assert has_shell_suggestion

    def test_no_suggestions_when_balanced(self):
        """No suggestions when context is well-balanced."""
        state = AgentState()
        state.add_system("System " + "x" * 1000)
        state.add_user("User request " + "y" * 500)
        state.add_assistant("Response " + "z" * 500)
        analysis = analyze_context(state)
        assert len(analysis.suggestions) == 0

    def test_format_for_model_empty_when_no_suggestions(self):
        state = AgentState()
        analysis = analyze_context(state)
        assert analysis.format_for_model() == ""

    def test_format_for_model_has_header(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("usr")
        for _ in range(10):
            state.conversation.append(Message(
                role="tool_result",
                content="[file_read] " + "x" * 5000,
            ))
        analysis = analyze_context(state)
        if analysis.suggestions:
            formatted = analysis.format_for_model()
            assert "[CONTEXT OPTIMIZATION]" in formatted

    def test_max_5_suggestions(self):
        """Suggestions capped at 5."""
        state = AgentState()
        state.add_system("s")
        state.add_user("u")
        # Create a state that triggers many suggestions
        for tool in ("file_read", "shell_exec", "match_grep", "match_glob"):
            for _ in range(10):
                state.add_assistant("c", tool_call={"function": {"name": tool, "arguments": {}}})
                state.conversation.append(Message(
                    role="tool_result", content=f"[{tool}] " + "x" * 3000,
                ))
        analysis = analyze_context(state)
        assert len(analysis.suggestions) <= 5
