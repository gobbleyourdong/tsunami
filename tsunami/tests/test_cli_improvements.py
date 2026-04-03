"""Tests for Chunk 11: CLI Improvements.

Verifies:
- Slash command parsing and handling
- /attach and /detach file management
- /trace view formatting
- /status output
- Tab completion setup
- CLI state management
"""

import os
import tempfile

from tsunami.cli_commands import (
    CLIState,
    SLASH_COMMANDS,
    handle_slash_command,
    format_trace,
    format_status,
    format_help,
    setup_tab_completion,
)


class TestCLIState:
    """CLI state management."""

    def test_initial_state(self):
        state = CLIState()
        assert state.attached_files == {}
        assert state.trace == []
        assert state.session_start > 0

    def test_attach_file(self):
        state = CLIState()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\nline 2")
            f.flush()
            result = state.attach(f.name)
        assert "Attached" in result
        assert "2 lines" in result
        assert f.name in state.attached_files
        os.unlink(f.name)

    def test_attach_nonexistent(self):
        state = CLIState()
        result = state.attach("/nonexistent/file.txt")
        assert "not found" in result.lower()

    def test_detach(self):
        state = CLIState()
        state.attached_files["test.txt"] = "content"
        result = state.detach()
        assert "1 file" in result
        assert len(state.attached_files) == 0

    def test_detach_empty(self):
        state = CLIState()
        result = state.detach()
        assert "No files" in result

    def test_get_attachment_block(self):
        state = CLIState()
        state.attached_files["src/App.tsx"] = "const App = () => <div/>"
        block = state.get_attachment_block()
        assert "ATTACHED: src/App.tsx" in block
        assert "const App" in block
        # Should clear after retrieval
        assert state.get_attachment_block() is None

    def test_record_tool_call(self):
        state = CLIState()
        state.record_tool_call("file_write", {"path": "test.ts"}, 150.5, True)
        assert len(state.trace) == 1
        assert state.trace[0]["tool"] == "file_write"
        assert state.trace[0]["duration_ms"] == 150.5
        assert state.trace[0]["success"] is True

    def test_trace_trimming(self):
        state = CLIState()
        for i in range(150):
            state.record_tool_call("tool", {}, float(i), True)
        assert len(state.trace) <= 100


class TestSlashCommands:
    """Slash command handling."""

    def test_attach_command(self):
        state = CLIState()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            f.flush()
            result = handle_slash_command(f"/attach {f.name}", state)
        assert "Attached" in result
        os.unlink(f.name)

    def test_attach_no_arg(self):
        state = CLIState()
        result = handle_slash_command("/attach", state)
        assert "Usage" in result

    def test_detach_command(self):
        state = CLIState()
        state.attached_files["test"] = "x"
        result = handle_slash_command("/detach", state)
        assert "1 file" in result

    def test_trace_command(self):
        state = CLIState()
        state.record_tool_call("file_write", {"path": "a.ts"}, 100, True)
        state.record_tool_call("shell_exec", {"command": "npm build"}, 2500, False)
        result = handle_slash_command("/trace", state)
        assert "file_write" in result
        assert "shell_exec" in result

    def test_trace_with_n(self):
        state = CLIState()
        for i in range(20):
            state.record_tool_call(f"tool_{i}", {}, float(i), True)
        result = handle_slash_command("/trace 5", state)
        assert "5 tool calls" in result

    def test_help_command(self):
        state = CLIState()
        result = handle_slash_command("/help", state)
        assert "/attach" in result
        assert "/status" in result
        assert "/trace" in result

    def test_status_command(self):
        state = CLIState()
        result = handle_slash_command("/status", state)
        assert "Uptime" in result
        assert "Tool calls" in result

    def test_quit_command(self):
        state = CLIState()
        result = handle_slash_command("/quit", state)
        assert result == "__QUIT__"

    def test_non_command_returns_none(self):
        state = CLIState()
        result = handle_slash_command("build a weather app", state)
        assert result is None

    def test_case_insensitive(self):
        state = CLIState()
        result = handle_slash_command("/HELP", state)
        assert "/attach" in result

    def test_clear_command(self):
        state = CLIState()
        result = handle_slash_command("/clear", state)
        assert "No active agent" in result


class TestFormatTrace:
    """Trace view formatting."""

    def test_empty_trace(self):
        state = CLIState()
        result = format_trace(state)
        assert "No tool calls" in result

    def test_formatted_output(self):
        state = CLIState()
        state.record_tool_call("file_write", {"path": "App.tsx"}, 200, True)
        result = format_trace(state)
        assert "OK" in result
        assert "file_write" in result
        assert "200" in result

    def test_error_shown(self):
        state = CLIState()
        state.record_tool_call("shell_exec", {"command": "npm build"}, 5000, False)
        result = format_trace(state)
        assert "ERR" in result


class TestFormatStatus:
    """Status output formatting."""

    def test_cli_state_only(self):
        state = CLIState()
        result = format_status(state=state)
        assert "Uptime" in result
        assert "Tool calls" in result

    def test_with_none_agent(self):
        result = format_status(agent=None, state=CLIState())
        assert "Status" in result


class TestFormatHelp:
    """Help text."""

    def test_lists_all_commands(self):
        help_text = format_help()
        for cmd in ["/attach", "/detach", "/status", "/trace", "/sessions", "/clear", "/help", "/quit"]:
            assert cmd in help_text


class TestTabCompletion:
    """Tab completion setup."""

    def test_setup_returns_bool(self):
        result = setup_tab_completion()
        assert isinstance(result, bool)

    def test_slash_commands_list(self):
        assert "/attach" in SLASH_COMMANDS
        assert "/status" in SLASH_COMMANDS
        assert "/trace" in SLASH_COMMANDS
        assert "/help" in SLASH_COMMANDS
        assert len(SLASH_COMMANDS) >= 7
