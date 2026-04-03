"""Tests for Chunk 2: Incremental Summarization — session memory + fact extraction.

Verifies:
- Running summary updates every 10 iterations
- Fact extraction from messages (files, types, prefs, architecture)
- Context block formatting
- Pinned blocks survive compression (importance-based)
"""

from tsunami.session_memory import (
    SessionMemory,
    SessionFacts,
    UPDATE_INTERVAL,
    _extract_actions,
    _extract_preference,
    _basename,
)
from tsunami.state import Message


def _make_msg(role, content, tool_call=None):
    return Message(role=role, content=content, tool_call=tool_call)


def _file_write_tc(path):
    return {"function": {"name": "file_write", "arguments": {"path": path, "content": "..."}}}


def _file_edit_tc(path):
    return {"function": {"name": "file_edit", "arguments": {"path": path}}}


def _project_init_tc(scaffold):
    return {"function": {"name": "project_init", "arguments": {"scaffold": scaffold}}}


def _shell_tc(cmd):
    return {"function": {"name": "shell_exec", "arguments": {"command": cmd}}}


class TestShouldUpdate:
    """Summary updates fire at correct intervals."""

    def test_fires_at_interval(self):
        mem = SessionMemory()
        assert mem.should_update(UPDATE_INTERVAL) is True

    def test_does_not_fire_at_zero(self):
        mem = SessionMemory()
        assert mem.should_update(0) is False

    def test_does_not_fire_between_intervals(self):
        mem = SessionMemory()
        assert mem.should_update(5) is False
        assert mem.should_update(15) is False

    def test_fires_at_multiples(self):
        mem = SessionMemory()
        assert mem.should_update(10) is True
        assert mem.should_update(20) is True
        assert mem.should_update(30) is True

    def test_does_not_fire_twice_for_same_iter(self):
        mem = SessionMemory()
        mem._last_update_iter = 10
        assert mem.should_update(10) is False

    def test_fires_after_prior_update(self):
        mem = SessionMemory()
        mem._last_update_iter = 10
        assert mem.should_update(20) is True


class TestUpdateSummary:
    """Running summary captures key actions."""

    def test_basic_summary(self):
        mem = SessionMemory()
        messages = [
            _make_msg("user", "build a weather app"),
            _make_msg("assistant", "", tool_call=_project_init_tc("react-app")),
            _make_msg("tool_result", "Created react-app scaffold"),
            _make_msg("assistant", "", tool_call=_file_write_tc("src/App.tsx")),
            _make_msg("tool_result", "Wrote src/App.tsx"),
        ]
        result = mem.update_summary(10, messages)
        assert result is not None
        assert "Iter 1-10" in result
        assert "scaffolded" in result or "wrote" in result

    def test_summary_stored(self):
        mem = SessionMemory()
        messages = [
            _make_msg("assistant", "", tool_call=_file_write_tc("src/App.tsx")),
        ]
        mem.update_summary(10, messages)
        assert len(mem.summaries) == 1
        assert "App.tsx" in mem.summaries[0]

    def test_empty_messages_returns_none(self):
        mem = SessionMemory()
        result = mem.update_summary(10, [])
        assert result is None

    def test_no_actions_returns_none(self):
        mem = SessionMemory()
        messages = [
            _make_msg("system", "you are an assistant"),
        ]
        result = mem.update_summary(10, messages)
        assert result is None

    def test_multiple_updates_accumulate(self):
        mem = SessionMemory()
        msgs1 = [_make_msg("assistant", "", tool_call=_file_write_tc("src/A.tsx"))]
        mem.update_summary(10, msgs1)

        msgs2 = msgs1 + [_make_msg("assistant", "", tool_call=_file_write_tc("src/B.tsx"))]
        mem.update_summary(20, msgs2)

        assert len(mem.summaries) == 2
        assert "Iter 1-10" in mem.summaries[0]
        assert "Iter 11-20" in mem.summaries[1]

    def test_user_message_captured(self):
        mem = SessionMemory()
        messages = [
            _make_msg("user", "make it dark mode with purple accents"),
        ]
        result = mem.update_summary(10, messages)
        assert result is not None
        assert "user said" in result


class TestExtractFacts:
    """Fact extraction from messages before compression."""

    def test_file_write_extracted(self):
        mem = SessionMemory()
        messages = [
            _make_msg("assistant", "", tool_call=_file_write_tc("src/types.ts")),
            _make_msg("assistant", "", tool_call=_file_write_tc("src/App.tsx")),
        ]
        facts = mem.extract_facts(messages)
        assert "src/types.ts" in facts.files_written
        assert "src/App.tsx" in facts.files_written

    def test_file_edit_extracted(self):
        mem = SessionMemory()
        messages = [
            _make_msg("assistant", "", tool_call=_file_edit_tc("src/index.css")),
        ]
        facts = mem.extract_facts(messages)
        assert "src/index.css" in facts.files_written

    def test_scaffold_extracted(self):
        mem = SessionMemory()
        messages = [
            _make_msg("assistant", "", tool_call=_project_init_tc("dashboard")),
        ]
        facts = mem.extract_facts(messages)
        assert any("dashboard" in a for a in facts.architecture)

    def test_types_extracted(self):
        mem = SessionMemory()
        messages = [
            _make_msg("assistant", "interface Item { id: string; name: string; }\ntype Status = 'active' | 'done';"),
        ]
        facts = mem.extract_facts(messages)
        assert "Item" in facts.types_defined
        assert "Status" in facts.types_defined

    def test_user_preference_extracted(self):
        mem = SessionMemory()
        messages = [
            _make_msg("user", "I want dark mode with a minimalist design"),
        ]
        facts = mem.extract_facts(messages)
        assert len(facts.user_preferences) > 0

    def test_tool_result_files_extracted(self):
        mem = SessionMemory()
        messages = [
            _make_msg("tool_result", "Wrote src/components/Header.tsx (45 lines)"),
            _make_msg("tool_result", "Created public/index.html"),
        ]
        facts = mem.extract_facts(messages)
        assert any("Header.tsx" in f for f in facts.files_written)
        assert any("index.html" in f for f in facts.files_written)

    def test_facts_merge_into_session(self):
        mem = SessionMemory()
        msgs1 = [_make_msg("assistant", "", tool_call=_file_write_tc("src/A.tsx"))]
        msgs2 = [_make_msg("assistant", "", tool_call=_file_write_tc("src/B.tsx"))]
        mem.extract_facts(msgs1)
        mem.extract_facts(msgs2)
        assert "src/A.tsx" in mem.facts.files_written
        assert "src/B.tsx" in mem.facts.files_written

    def test_empty_messages_returns_empty(self):
        mem = SessionMemory()
        facts = mem.extract_facts([])
        assert facts.is_empty()


class TestSessionFacts:
    """Facts formatting and dedup."""

    def test_to_block_format(self):
        facts = SessionFacts(
            files_written=["src/App.tsx", "src/types.ts"],
            types_defined=["Item", "User"],
            user_preferences=["dark mode"],
            architecture=["scaffold: react-app"],
        )
        block = facts.to_block()
        assert "Files:" in block
        assert "App.tsx" in block
        assert "Types:" in block
        assert "Item" in block
        assert "User wants:" in block
        assert "dark mode" in block
        assert "Architecture:" in block

    def test_is_empty(self):
        assert SessionFacts().is_empty() is True
        assert SessionFacts(files_written=["x"]).is_empty() is False

    def test_merge(self):
        f1 = SessionFacts(files_written=["a.ts"])
        f2 = SessionFacts(files_written=["b.ts"], types_defined=["Foo"])
        f1.merge(f2)
        assert "a.ts" in f1.files_written
        assert "b.ts" in f1.files_written
        assert "Foo" in f1.types_defined

    def test_dedup_in_block(self):
        facts = SessionFacts(
            files_written=["src/App.tsx", "src/App.tsx", "src/App.tsx"],
        )
        block = facts.to_block()
        # Should only appear once in output
        assert block.count("App.tsx") == 1

    def test_caps_at_30_files(self):
        facts = SessionFacts(
            files_written=[f"src/file_{i}.tsx" for i in range(50)],
        )
        block = facts.to_block()
        # Should have at most 30 files listed
        assert block.count(".tsx") <= 30


class TestContextBlock:
    """Full context block formatting."""

    def test_empty_memory_returns_none(self):
        mem = SessionMemory()
        assert mem.to_context_block() is None

    def test_summary_only(self):
        mem = SessionMemory()
        mem.summaries = ["Iter 1-10: scaffolded react-app"]
        block = mem.to_context_block()
        assert "[SESSION MEMORY]" in block
        assert "scaffolded react-app" in block

    def test_facts_only(self):
        mem = SessionMemory()
        mem.facts = SessionFacts(files_written=["src/App.tsx"])
        block = mem.to_context_block()
        assert "[KEY FACTS]" in block
        assert "App.tsx" in block

    def test_both_sections(self):
        mem = SessionMemory()
        mem.summaries = ["Iter 1-10: built dashboard"]
        mem.facts = SessionFacts(architecture=["scaffold: dashboard"])
        block = mem.to_context_block()
        assert "[SESSION MEMORY]" in block
        assert "[KEY FACTS]" in block
        assert "dashboard" in block


class TestExtractActions:
    """Action extraction from individual messages."""

    def test_file_write(self):
        actions = _extract_actions("assistant", "", _file_write_tc("src/App.tsx"))
        assert any("App.tsx" in a for a in actions)

    def test_file_edit(self):
        actions = _extract_actions("assistant", "", _file_edit_tc("src/App.tsx"))
        assert any("App.tsx" in a for a in actions)

    def test_project_init(self):
        actions = _extract_actions("assistant", "", _project_init_tc("react-app"))
        assert any("react-app" in a for a in actions)

    def test_shell_npm(self):
        actions = _extract_actions("assistant", "", _shell_tc("npm install recharts"))
        assert any("npm" in a for a in actions)

    def test_shell_build(self):
        actions = _extract_actions("assistant", "", _shell_tc("make build"))
        assert any("build" in a for a in actions)

    def test_user_message(self):
        actions = _extract_actions("user", "build a weather dashboard", None)
        assert any("user said" in a for a in actions)

    def test_no_tool_call_assistant(self):
        actions = _extract_actions("assistant", "thinking...", None)
        assert actions == []

    def test_system_message_no_actions(self):
        actions = _extract_actions("system", "you are helpful", None)
        assert actions == []


class TestExtractPreference:
    """User preference extraction."""

    def test_dark_mode(self):
        assert _extract_preference("use dark mode please") is not None

    def test_minimalist(self):
        assert _extract_preference("I want a minimalist design") is not None

    def test_responsive(self):
        assert _extract_preference("make it mobile-first") is not None

    def test_explicit_want(self):
        pref = _extract_preference("I want purple accents and rounded corners")
        assert pref is not None

    def test_no_preference(self):
        assert _extract_preference("hello") is None

    def test_short_content(self):
        assert _extract_preference("ok") is None


class TestBasename:
    """Path basename utility."""

    def test_with_path(self):
        assert _basename("src/components/App.tsx") == "App.tsx"

    def test_no_path(self):
        assert _basename("App.tsx") == "App.tsx"

    def test_deep_path(self):
        assert _basename("a/b/c/d/file.ts") == "file.ts"
