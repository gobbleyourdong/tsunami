"""Tests for notification system (ported from Claude Code's notifier.ts)."""

import pytest

from tsunami.notifier import (
    detect_terminal,
    notify,
    notify_task_complete,
    notify_error,
    TASK_COMPLETE,
    TASK_ERROR,
    LONG_OPERATION,
)


class TestDetectTerminal:
    """Terminal type detection from environment."""

    def test_returns_string(self):
        result = detect_terminal()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_known_types(self):
        # Should return one of the known types
        known = {"iterm", "kitty", "ghostty", "apple_terminal", "linux_desktop", "basic"}
        result = detect_terminal()
        assert result in known


class TestNotify:
    """Notification dispatch."""

    def test_returns_result_dict(self):
        result = notify("Test message", bell=False, desktop=False)
        assert "message" in result
        assert "title" in result
        assert "type" in result
        assert "channels" in result

    def test_message_preserved(self):
        result = notify("Hello world", bell=False, desktop=False)
        assert result["message"] == "Hello world"

    def test_custom_title(self):
        result = notify("msg", title="Custom", bell=False, desktop=False)
        assert result["title"] == "Custom"

    def test_notification_type(self):
        result = notify("msg", notification_type=TASK_ERROR, bell=False, desktop=False)
        assert result["type"] == TASK_ERROR

    def test_bell_channel(self):
        result = notify("msg", bell=True, desktop=False)
        assert "bell" in result["channels"]

    def test_no_bell(self):
        result = notify("msg", bell=False, desktop=False)
        assert "bell" not in result["channels"]


class TestConvenienceFunctions:
    """Shorthand notification functions."""

    def test_notify_task_complete(self):
        result = notify_task_complete("All done")
        assert result["type"] == TASK_COMPLETE
        assert "All done" in result["message"]

    def test_notify_error(self):
        result = notify_error("Something broke")
        assert result["type"] == TASK_ERROR
        assert "Something broke" in result["message"]

    def test_default_message(self):
        result = notify_task_complete()
        assert "Task complete" in result["message"]
