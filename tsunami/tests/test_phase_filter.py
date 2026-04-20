"""Tests for phase-based tool filtering.

Verifies:
- Phase detection from tool usage patterns
- Per-phase tool subsets
- Phase transition notes
"""

from tsunami.phase_filter import (
    detect_phase,
    get_phase_tools,
    filter_tools_for_phase,
    generate_phase_note,
    PHASE_TOOLS,
    UNIVERSAL_TOOLS,
)


class TestPhaseDetection:
    """Detect phase from tool history."""

    def test_few_tools_defaults_to_research(self):
        assert detect_phase(["file_read"]) == "RESEARCH"
        assert detect_phase([]) == "RESEARCH"

    def test_research_phase(self):
        history = ["search_web", "file_read", "match_grep", "search_web",
                    "file_read", "search_web", "match_glob", "file_read",
                    "search_web", "file_read"]
        assert detect_phase(history) == "RESEARCH"

    def test_build_phase(self):
        history = ["file_write", "file_edit", "file_write", "shell_exec",
                    "file_write", "file_edit", "project_init", "file_write",
                    "file_edit", "file_write"]
        assert detect_phase(history) == "BUILD"

    def test_verify_phase(self):
        # Some writes in history, then lots of shell_exec
        history = ["file_write", "file_edit", "file_write",
                    "shell_exec", "shell_exec", "shell_exec",
                    "shell_exec", "shell_exec", "shell_exec",
                    "shell_exec"]
        assert detect_phase(history) == "VERIFY"

    def test_deliver_phase(self):
        history = ["file_write", "shell_exec", "message_result"]
        assert detect_phase(history) == "DELIVER"

    def test_plan_phase(self):
        # PLAN phase = predominantly message_chat (clarification before building).
        # Old test referenced plan_update / message_info which were dropped in
        # the 11-tool cleanup; updated to the current PLAN tool set.
        history = ["message_chat"] * 8 + ["file_read", "search_web"]
        assert detect_phase(history) == "PLAN"


class TestPhaseTools:
    """Per-phase tool subsets."""

    def test_research_has_search(self):
        tools = get_phase_tools("RESEARCH")
        assert "search_web" in tools
        assert "file_read" in tools

    def test_build_has_write(self):
        tools = get_phase_tools("BUILD")
        assert "file_write" in tools
        assert "file_edit" in tools

    def test_verify_has_shell(self):
        tools = get_phase_tools("VERIFY")
        assert "shell_exec" in tools

    def test_deliver_has_result(self):
        tools = get_phase_tools("DELIVER")
        assert "message_result" in tools

    def test_universal_tools_always_present(self):
        for phase in PHASE_TOOLS:
            tools = get_phase_tools(phase)
            for u in UNIVERSAL_TOOLS:
                assert u in tools, f"{u} missing from {phase}"

    def test_unknown_phase_returns_universal(self):
        tools = get_phase_tools("NONEXISTENT")
        assert tools == UNIVERSAL_TOOLS


class TestFilterTools:
    """Filter available tools based on phase."""

    def test_build_phase_no_filtering(self):
        all_tools = ["file_write", "file_read", "search_web", "shell_exec"]
        phase, filtered = filter_tools_for_phase(all_tools, ["file_write"] * 10)
        assert phase == "BUILD"
        assert filtered == all_tools  # no filtering in BUILD

    def test_research_phase_filters(self):
        all_tools = ["file_write", "file_read", "search_web", "shell_exec", "message_ask"]
        phase, filtered = filter_tools_for_phase(all_tools, ["search_web"] * 10)
        assert phase == "RESEARCH"
        assert "search_web" in filtered
        assert "file_read" in filtered

    def test_safety_minimum_tools(self):
        """If filtering removes too many tools, keep all."""
        all_tools = ["some_rare_tool"]
        phase, filtered = filter_tools_for_phase(all_tools, ["search_web"] * 10)
        assert filtered == all_tools  # safety: kept all


class TestPhaseNotes:
    """Phase transition guidance notes."""

    def test_no_note_with_few_tools(self):
        assert generate_phase_note("RESEARCH", ["file_read"]) is None

    def test_research_too_long(self):
        history = ["search_web"] * 20
        note = generate_phase_note("RESEARCH", history)
        assert note is not None
        assert "BUILD" in note

    def test_build_needs_verify(self):
        history = ["file_write"] * 10
        note = generate_phase_note("BUILD", history)
        assert note is not None
        assert "build check" in note.lower() or "verify" in note.lower()

    def test_no_note_during_normal_build(self):
        history = ["file_write", "shell_exec", "file_edit", "shell_exec", "file_write"]
        note = generate_phase_note("BUILD", history)
        assert note is None  # shell_exec in recent, no need to nag


# NB: TestModelCapability removed 2026-04-13 alongside ModelCapability itself —
# the probe was tested-but-never-wired-into-agent dead code. If we ever want
# capability gating, drive it from real eval scores, not a one-off probe.
