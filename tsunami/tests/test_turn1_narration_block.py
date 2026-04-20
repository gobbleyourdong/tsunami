"""Turn-1 message_result narration block (pure-logic version).

Regression target: twice-in-a-row on 2026-04-20, small-model drones called
`message_result("Starting Phase 1: Scaffolding ORBIT design studio project.")`
as their very first tool call. tsunami's "short conversational reply" path
treated that as a legitimate chat answer, marked the task complete, and the
run exited at 0 seconds with no deliverable. Every speed-budget layer
downstream never ran.

The fix (tsunami/agent.py, in the message_result handler): when the task
text looks like a build request (contains words like "build", "create",
"landing", "dashboard", etc.) AND the drone has done nothing yet
(tool_history at most 1 entry), intercept the message_result, inject a
hard "call project_init" nudge, and decrement _delivery_attempts so the
drone gets another turn.

These tests cover the classification logic in isolation — no agent spin-up,
they just verify the pattern-match that fires the intercept.
"""


BUILD_HINTS = ("build", "create", "make a", "scaffold", "landing",
               "website", "dashboard", "app ", "page", "portfolio",
               "brand", "studio")


def _looks_like_build(user_req: str) -> bool:
    """Mirror of the inline check in agent.py."""
    lower = user_req.lower()
    return any(h in lower for h in BUILD_HINTS)


class TestLooksLikeBuild:
    def test_explicit_build(self):
        assert _looks_like_build("Build a minimalist landing page for ORBIT")

    def test_with_website_word(self):
        assert _looks_like_build("make me a website for a design studio")

    def test_dashboard_task(self):
        assert _looks_like_build("Create a weather dashboard with 3 cards")

    def test_brand_page(self):
        assert _looks_like_build("BRAND: ORBIT — hero, gallery, contact")

    def test_portfolio_task(self):
        assert _looks_like_build("Portfolio site with work showcase")

    def test_non_build_greeting(self):
        assert not _looks_like_build("Hello! How are you today?")

    def test_non_build_question(self):
        assert not _looks_like_build("What is the capital of France?")

    def test_research_request(self):
        """Research / Q&A shouldn't trigger the build guard."""
        # "app" with trailing space is a build hint; "application" shouldn't be.
        assert not _looks_like_build("explain how diffusion models work")

    def test_case_insensitive(self):
        assert _looks_like_build("BUILD A SIMPLE LANDING PAGE")


class TestInterceptConditions:
    """The intercept needs BOTH looks_like_build AND nothing_built_yet."""

    def test_intercept_on_turn_1_build_task(self):
        """tool_history empty + build task → intercept."""
        tool_history: list[str] = []
        user_req = "Build a landing page for ORBIT"
        nothing_built_yet = len(tool_history) <= 1
        assert _looks_like_build(user_req) and nothing_built_yet

    def test_no_intercept_mid_build(self):
        """tool_history with real work → don't intercept."""
        tool_history = ["project_init", "file_write", "shell_exec"]
        nothing_built_yet = len(tool_history) <= 1
        assert not nothing_built_yet

    def test_no_intercept_on_chat(self):
        """Chat-like task + message_result is a legitimate reply."""
        tool_history: list[str] = []
        user_req = "what's 2+2?"
        nothing_built_yet = len(tool_history) <= 1
        assert not _looks_like_build(user_req)
        # Even though nothing_built_yet is True, looks_like_build gates it.
        _ = nothing_built_yet

    def test_one_tool_entry_still_counts_as_nothing(self):
        """The system auto-tracks 'message_result' in history; one entry still
        qualifies as nothing-built. Threshold is <= 1."""
        tool_history = ["message_result"]
        nothing_built_yet = len(tool_history) <= 1
        assert nothing_built_yet

    def test_two_tool_entries_no_longer_nothing(self):
        """Two real tool calls means the drone started working — no intercept."""
        tool_history = ["project_init", "file_write"]
        nothing_built_yet = len(tool_history) <= 1
        assert not nothing_built_yet
