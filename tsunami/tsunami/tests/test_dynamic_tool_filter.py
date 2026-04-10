"""Tests for Chunk 4: Dynamic Tool Filtering.

Verifies:
- Tool recording (before/after tension)
- Phase detection (RESEARCH, BUILD, VERIFY, MIXED)
- Guidance generation (effective/ineffective tools)
- Research loop detection ("SWITCH TO BUILDING")
- Build momentum detection ("GOOD MOMENTUM")
"""

from tsunami.dynamic_tool_filter import (
    DynamicToolFilter,
    ToolRecord,
    RESEARCH_TOOLS,
    BUILD_TOOLS,
    VERIFY_TOOLS,
    WINDOW_SIZE,
)


class TestToolRecording:
    """Record tool calls with tension deltas."""

    def test_record_basic(self):
        f = DynamicToolFilter()
        f.record_before(0.5)
        f.record_after("file_write", 0.3, True)
        assert len(f.records) == 1
        assert f.records[0].name == "file_write"
        assert f.records[0].tension_before == 0.5
        assert f.records[0].tension_after == 0.3
        assert f.records[0].success is True

    def test_tension_delta_positive_when_tension_drops(self):
        r = ToolRecord(name="file_write", tension_before=0.5, tension_after=0.2, success=True)
        assert r.tension_delta == 0.3  # positive = good

    def test_tension_delta_negative_when_tension_rises(self):
        r = ToolRecord(name="search_web", tension_before=0.2, tension_after=0.5, success=True)
        assert r.tension_delta == -0.3  # negative = bad

    def test_no_before_uses_after(self):
        """If record_before wasn't called, before defaults to after."""
        f = DynamicToolFilter()
        f.record_after("file_read", 0.4, True)
        assert f.records[0].tension_before == 0.4
        assert f.records[0].tension_delta == 0.0

    def test_window_trimming(self):
        f = DynamicToolFilter(window_size=5)
        for i in range(50):
            f.record_before(0.3)
            f.record_after("file_write", 0.2, True)
        # Should have trimmed down
        assert len(f.records) <= 15  # window * 3 max


class TestPhaseDetection:
    """Detect current phase based on tool usage patterns."""

    def test_unknown_with_few_records(self):
        f = DynamicToolFilter()
        f.record_after("file_write", 0.3, True)
        assert f.detect_phase() == "UNKNOWN"

    def test_research_phase(self):
        f = DynamicToolFilter()
        for _ in range(8):
            f.record_after("search_web", 0.3, True)
        for _ in range(2):
            f.record_after("file_read", 0.2, True)
        assert f.detect_phase() == "RESEARCH"

    def test_build_phase(self):
        f = DynamicToolFilter()
        for _ in range(8):
            f.record_after("file_write", 0.2, True)
        for _ in range(2):
            f.record_after("file_edit", 0.2, True)
        assert f.detect_phase() == "BUILD"

    def test_verify_phase(self):
        f = DynamicToolFilter()
        for _ in range(5):
            f.record_after("shell_exec", 0.3, True)
        for _ in range(3):
            f.record_after("file_read", 0.2, True)
        for _ in range(2):
            f.record_after("shell_exec", 0.3, True)
        assert f.detect_phase() == "VERIFY"

    def test_mixed_phase(self):
        f = DynamicToolFilter()
        tools = ["file_write", "search_web", "shell_exec", "file_read",
                 "file_edit", "search_web", "shell_exec", "file_write",
                 "file_read", "shell_exec"]
        for t in tools:
            f.record_after(t, 0.3, True)
        assert f.detect_phase() == "MIXED"


class TestGuidance:
    """Guidance generation based on patterns."""

    def test_no_guidance_with_few_records(self):
        f = DynamicToolFilter()
        f.record_after("file_write", 0.2, True)
        assert f.get_guidance() is None

    def test_switch_to_building(self):
        """PLAN.md: >60% search/read → SWITCH TO BUILDING."""
        f = DynamicToolFilter()
        for _ in range(7):
            f.record_before(0.4)
            f.record_after("search_web", 0.45, True)
        for _ in range(3):
            f.record_before(0.4)
            f.record_after("file_read", 0.42, True)
        guidance = f.get_guidance()
        assert guidance is not None
        assert "SWITCH TO BUILDING" in guidance

    def test_good_momentum(self):
        """PLAN.md: >80% write/edit with success → GOOD MOMENTUM."""
        f = DynamicToolFilter()
        for _ in range(9):
            f.record_before(0.3)
            f.record_after("file_write", 0.1, True)
        f.record_before(0.2)
        f.record_after("file_edit", 0.1, True)
        guidance = f.get_guidance()
        assert guidance is not None
        assert "GOOD MOMENTUM" in guidance

    def test_effective_tools_listed(self):
        f = DynamicToolFilter()
        # file_write consistently drops tension (good)
        for _ in range(5):
            f.record_before(0.5)
            f.record_after("file_write", 0.2, True)
        # search_web consistently raises tension (bad)
        for _ in range(5):
            f.record_before(0.2)
            f.record_after("search_web", 0.5, False)
        guidance = f.get_guidance()
        assert guidance is not None
        assert "TOOL GUIDANCE" in guidance
        assert "effective" in guidance.lower() or "ineffective" in guidance.lower()

    def test_no_guidance_when_balanced(self):
        """Even mix of tools with moderate tension → no strong guidance."""
        f = DynamicToolFilter()
        tools = ["file_write", "file_read", "shell_exec", "file_edit", "match_grep"]
        for t in tools * 2:
            f.record_before(0.3)
            f.record_after(t, 0.3, True)
        guidance = f.get_guidance()
        # May or may not have guidance, but shouldn't have phase warnings
        if guidance:
            assert "SWITCH TO BUILDING" not in guidance
            assert "GOOD MOMENTUM" not in guidance


class TestSummary:
    """Summary stats for logging."""

    def test_empty_summary(self):
        f = DynamicToolFilter()
        s = f.summary()
        assert s["total"] == 0

    def test_populated_summary(self):
        f = DynamicToolFilter()
        for _ in range(5):
            f.record_before(0.3)
            f.record_after("file_write", 0.2, True)
        s = f.summary()
        assert s["total"] == 5
        assert s["success_rate"] == 1.0
        assert s["phase"] in ("BUILD", "UNKNOWN", "MIXED")
        assert "avg_tension_delta" in s


class TestToolCategories:
    """Verify tool categorization constants."""

    def test_research_tools(self):
        assert "search_web" in RESEARCH_TOOLS
        assert "file_read" in RESEARCH_TOOLS
        assert "match_grep" in RESEARCH_TOOLS

    def test_build_tools(self):
        assert "file_write" in BUILD_TOOLS
        assert "file_edit" in BUILD_TOOLS
        assert "project_init" in BUILD_TOOLS

    def test_verify_tools(self):
        assert "shell_exec" in VERIFY_TOOLS

    def test_no_overlap(self):
        assert not (RESEARCH_TOOLS & BUILD_TOOLS)
        assert not (BUILD_TOOLS & VERIFY_TOOLS)
