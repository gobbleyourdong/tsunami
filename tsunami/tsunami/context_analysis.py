"""Context analysis — analyze token usage and suggest optimizations.

Analyzes which tools consume the most context tokens and generates
actionable suggestions for the model to reduce bloat. This helps
the agent self-regulate its context usage during long sessions.

The analysis runs periodically and injects suggestions into the
conversation when context is getting tight.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .state import AgentState, Message
from .token_estimation import estimate_tokens_for_message

log = logging.getLogger("tsunami.context_analysis")

# Thresholds for generating suggestions
TOOL_RESULT_BLOAT_THRESHOLD = 0.15  # warn if any tool uses >15% of context
READ_BLOAT_THRESHOLD = 0.20  # warn if file_read results use >20%
TOTAL_BLOAT_THRESHOLD = 0.60  # warn if tool results are >60% of total


@dataclass
class ToolUsageBreakdown:
    """Token usage by tool name."""
    tool_name: str
    call_count: int = 0
    result_tokens: int = 0
    call_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.result_tokens + self.call_tokens


@dataclass
class ContextAnalysis:
    """Complete context analysis result."""
    total_tokens: int = 0
    system_tokens: int = 0
    user_tokens: int = 0
    assistant_tokens: int = 0
    tool_result_tokens: int = 0
    tool_usage: dict[str, ToolUsageBreakdown] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)

    @property
    def tool_result_fraction(self) -> float:
        if self.total_tokens == 0:
            return 0.0
        return self.tool_result_tokens / self.total_tokens

    def format_summary(self) -> str:
        """Human-readable summary of context usage."""
        lines = [f"Context: {self.total_tokens:,} tokens"]
        lines.append(f"  System: {self.system_tokens:,}")
        lines.append(f"  User: {self.user_tokens:,}")
        lines.append(f"  Assistant: {self.assistant_tokens:,}")
        lines.append(f"  Tool results: {self.tool_result_tokens:,} ({self.tool_result_fraction:.0%})")

        if self.tool_usage:
            lines.append("  By tool:")
            sorted_tools = sorted(
                self.tool_usage.values(),
                key=lambda t: t.total_tokens,
                reverse=True,
            )
            for tu in sorted_tools[:5]:
                lines.append(f"    {tu.tool_name}: {tu.total_tokens:,} tokens ({tu.call_count} calls)")

        if self.suggestions:
            lines.append("  Suggestions:")
            for s in self.suggestions:
                lines.append(f"    - {s}")

        return "\n".join(lines)

    def format_for_model(self) -> str:
        """Compact format for injecting into conversation context."""
        if not self.suggestions:
            return ""
        parts = ["[CONTEXT OPTIMIZATION]"]
        parts.append(f"Token usage: {self.total_tokens:,} ({self.tool_result_fraction:.0%} tool results)")
        for s in self.suggestions:
            parts.append(f"- {s}")
        return "\n".join(parts)


def analyze_context(state: AgentState) -> ContextAnalysis:
    """Analyze the current conversation context for token usage patterns.

    Returns a ContextAnalysis with per-tool breakdown and suggestions.
    """
    analysis = ContextAnalysis()

    for m in state.conversation:
        tokens = estimate_tokens_for_message(m.role, m.content, m.tool_call)

        if m.role == "system":
            analysis.system_tokens += tokens
        elif m.role == "user":
            analysis.user_tokens += tokens
        elif m.role == "assistant":
            analysis.assistant_tokens += tokens
            # Track tool call tokens
            if m.tool_call:
                func = m.tool_call.get("function", m.tool_call)
                name = func.get("name", "unknown")
                if name not in analysis.tool_usage:
                    analysis.tool_usage[name] = ToolUsageBreakdown(tool_name=name)
                analysis.tool_usage[name].call_tokens += tokens
                analysis.tool_usage[name].call_count += 1
        elif m.role == "tool_result":
            analysis.tool_result_tokens += tokens
            # Extract tool name from result prefix "[tool_name]"
            name = _extract_tool_name(m.content)
            if name not in analysis.tool_usage:
                analysis.tool_usage[name] = ToolUsageBreakdown(tool_name=name)
            analysis.tool_usage[name].result_tokens += tokens

    analysis.total_tokens = (
        analysis.system_tokens + analysis.user_tokens
        + analysis.assistant_tokens + analysis.tool_result_tokens
    )

    # Generate suggestions based on usage patterns
    analysis.suggestions = _generate_suggestions(analysis)

    return analysis


def _extract_tool_name(content: str) -> str:
    """Extract tool name from '[tool_name] ...' prefix."""
    if content.startswith("[") and "]" in content[:50]:
        return content[1:content.index("]")]
    return "unknown"


def _generate_suggestions(analysis: ContextAnalysis) -> list[str]:
    """Generate context optimization suggestions based on usage patterns."""
    suggestions = []

    if analysis.total_tokens == 0:
        return suggestions

    # Overall tool result bloat
    if analysis.tool_result_fraction > TOTAL_BLOAT_THRESHOLD:
        suggestions.append(
            f"Tool results consume {analysis.tool_result_fraction:.0%} of context. "
            f"Save important findings to files and use shorter tool outputs."
        )

    # Per-tool suggestions
    for name, tu in analysis.tool_usage.items():
        frac = tu.result_tokens / max(analysis.total_tokens, 1)

        if name == "file_read" and frac > READ_BLOAT_THRESHOLD:
            suggestions.append(
                f"file_read uses {frac:.0%} of context. Use offset/limit to read "
                f"only the sections you need, or use match_grep to find specific content."
            )
        elif name == "shell_exec" and frac > TOOL_RESULT_BLOAT_THRESHOLD:
            suggestions.append(
                f"shell_exec output uses {frac:.0%} of context. Pipe through "
                f"head/tail/grep to reduce output size."
            )
        elif name == "match_grep" and frac > TOOL_RESULT_BLOAT_THRESHOLD:
            suggestions.append(
                f"match_grep uses {frac:.0%} of context. Use more specific "
                f"patterns or add a file glob filter."
            )
        elif name == "match_glob" and frac > TOOL_RESULT_BLOAT_THRESHOLD:
            suggestions.append(
                f"match_glob uses {frac:.0%} of context. Use more specific "
                f"patterns to reduce result count."
            )

    # High call count with low value
    for name, tu in analysis.tool_usage.items():
        if tu.call_count >= 10 and tu.result_tokens > 0:
            avg_tokens = tu.result_tokens // tu.call_count
            if avg_tokens < 20:
                suggestions.append(
                    f"{name} called {tu.call_count} times with tiny results. "
                    f"Consider batching operations."
                )

    return suggestions[:5]  # cap at 5 suggestions
