"""Tests for compaction analysis scratchpad stripping."""

import pytest

from tsunami.compression import strip_analysis_scratchpad, COMPACT_SYSTEM_PROMPT


class TestStripAnalysisScratchpad:
    """The <analysis> tag is stripped, only <summary> survives."""

    def test_strips_analysis_keeps_summary(self):
        text = (
            "<analysis>\n"
            "Let me think about what matters here...\n"
            "The key files are X, Y, Z.\n"
            "</analysis>\n"
            "<summary>\n"
            "1. Primary Request: Fix the login bug\n"
            "2. Files Modified: auth.py\n"
            "</summary>"
        )
        result = strip_analysis_scratchpad(text)
        assert "think about" not in result
        assert "Primary Request" in result
        assert "Fix the login bug" in result

    def test_no_tags_returns_as_is(self):
        """If model doesn't use tags, content passes through."""
        text = "1. Primary Request: Build a dashboard\n2. Files: app.py"
        result = strip_analysis_scratchpad(text)
        assert result == text

    def test_only_analysis_no_summary(self):
        """If only analysis tag, strip it and return rest."""
        text = "<analysis>thinking...</analysis>\nThe actual summary here."
        result = strip_analysis_scratchpad(text)
        assert "thinking" not in result
        assert "actual summary" in result

    def test_empty_analysis(self):
        text = "<analysis></analysis><summary>content</summary>"
        result = strip_analysis_scratchpad(text)
        assert result == "content"

    def test_multiline_analysis(self):
        text = (
            "<analysis>\n"
            "Line 1\n"
            "Line 2\n"
            "Line 3\n"
            "</analysis>\n"
            "<summary>\n"
            "Clean summary\n"
            "</summary>"
        )
        result = strip_analysis_scratchpad(text)
        assert "Line 1" not in result
        assert "Clean summary" in result

    def test_empty_input(self):
        assert strip_analysis_scratchpad("") == ""

    def test_whitespace_handling(self):
        text = "  <analysis> pad </analysis>  <summary>  result  </summary>  "
        result = strip_analysis_scratchpad(text)
        assert result == "result"

    def test_analysis_with_code_snippets(self):
        """Analysis might contain code — should all be stripped."""
        text = (
            "<analysis>\n"
            "The function looks like:\n"
            "```python\n"
            "def foo(): pass\n"
            "```\n"
            "</analysis>\n"
            "<summary>\n"
            "Modified foo() in bar.py\n"
            "</summary>"
        )
        result = strip_analysis_scratchpad(text)
        assert "def foo" not in result
        assert "Modified foo" in result


class TestCompactSystemPrompt:
    """The prompt instructs the model to use analysis+summary format."""

    def test_prompt_mentions_analysis(self):
        assert "<analysis>" in COMPACT_SYSTEM_PROMPT

    def test_prompt_mentions_summary(self):
        assert "<summary>" in COMPACT_SYSTEM_PROMPT

    def test_prompt_says_analysis_stripped(self):
        assert "stripped" in COMPACT_SYSTEM_PROMPT.lower()

    def test_prompt_has_all_sections(self):
        for section in [
            "Primary Request",
            "Technical Concepts",
            "Files",
            "Errors",
            "User Messages",
            "Pending Tasks",
            "Current Work",
        ]:
            assert section in COMPACT_SYSTEM_PROMPT

    def test_prompt_rejects_tools(self):
        assert "Do NOT call any tools" in COMPACT_SYSTEM_PROMPT
