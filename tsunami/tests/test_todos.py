"""Tests for todo/task tracking (ported from Claude Code's TodoWriteTool)."""

import json
import os
import tempfile
import pytest

from tsunami.todos import TodoList, TodoItem


class TestTodoList:
    """Basic CRUD operations."""

    def test_add_item(self):
        tl = TodoList()
        item = tl.add("Fix the bug")
        assert item.title == "Fix the bug"
        assert item.status == "pending"
        assert len(tl.items) == 1

    def test_add_multiple(self):
        tl = TodoList()
        tl.add("First")
        tl.add("Second")
        tl.add("Third")
        assert len(tl.items) == 3

    def test_unique_ids(self):
        tl = TodoList()
        a = tl.add("A")
        b = tl.add("B")
        assert a.id != b.id

    def test_update_status(self):
        tl = TodoList()
        item = tl.add("Task")
        tl.update(item.id, "in_progress")
        assert tl.items[0].status == "in_progress"

    def test_update_completed_sets_time(self):
        tl = TodoList()
        item = tl.add("Task")
        tl.update(item.id, "completed")
        assert item.completed_at is not None

    def test_update_nonexistent(self):
        tl = TodoList()
        result = tl.update("fake_id", "completed")
        assert result is None

    def test_get_item(self):
        tl = TodoList()
        item = tl.add("Test")
        found = tl.get(item.id)
        assert found is not None
        assert found.title == "Test"

    def test_get_nonexistent(self):
        tl = TodoList()
        assert tl.get("fake") is None


class TestTodoListFilters:
    """Filter by status."""

    def _build_list(self) -> TodoList:
        tl = TodoList()
        tl.add("Pending task")
        item2 = tl.add("In progress task")
        tl.update(item2.id, "in_progress")
        item3 = tl.add("Done task")
        tl.update(item3.id, "completed")
        tl.add("Another pending")
        return tl

    def test_pending(self):
        tl = self._build_list()
        assert len(tl.pending) == 2

    def test_in_progress(self):
        tl = self._build_list()
        assert len(tl.in_progress) == 1

    def test_completed(self):
        tl = self._build_list()
        assert len(tl.completed) == 1

    def test_all_done_false(self):
        tl = self._build_list()
        assert tl.all_done is False

    def test_all_done_true(self):
        tl = TodoList()
        item = tl.add("Only task")
        tl.update(item.id, "completed")
        assert tl.all_done is True

    def test_progress_fraction(self):
        tl = self._build_list()
        assert tl.progress_fraction == 0.25  # 1/4

    def test_progress_empty(self):
        tl = TodoList()
        assert tl.progress_fraction == 0.0


class TestTodoListSetAll:
    """Claude Code's TodoWriteTool pattern — replace all todos."""

    def test_set_all(self):
        tl = TodoList()
        tl.set_all([
            {"title": "Task A", "status": "completed"},
            {"title": "Task B", "status": "in_progress"},
            {"title": "Task C"},
        ])
        assert len(tl.items) == 3
        assert tl.items[0].status == "completed"
        assert tl.items[1].status == "in_progress"
        assert tl.items[2].status == "pending"

    def test_set_all_clears_previous(self):
        tl = TodoList()
        tl.add("Old task")
        tl.set_all([{"title": "New task"}])
        assert len(tl.items) == 1
        assert tl.items[0].title == "New task"


class TestTodoListFormatting:
    """Display and context injection."""

    def test_format_summary_empty(self):
        tl = TodoList()
        assert tl.format_summary() == "No tasks."

    def test_format_summary_with_items(self):
        tl = TodoList()
        tl.add("First")
        item = tl.add("Second")
        tl.update(item.id, "completed")
        summary = tl.format_summary()
        assert "[ ]" in summary  # pending
        assert "[x]" in summary  # completed
        assert "1/2" in summary
        assert "50%" in summary

    def test_format_for_context_empty(self):
        tl = TodoList()
        assert tl.format_for_context() == ""

    def test_format_for_context_has_header(self):
        tl = TodoList()
        tl.add("Task")
        ctx = tl.format_for_context()
        assert "[TASK PROGRESS]" in ctx

    def test_verification_nudge_threshold(self):
        tl = TodoList()
        for i in range(3):
            item = tl.add(f"Task {i}")
            tl.update(item.id, "completed")
        tl.add("Remaining task")
        assert tl.should_nudge_verification() is True

    def test_no_nudge_when_all_done(self):
        tl = TodoList()
        for i in range(3):
            item = tl.add(f"Task {i}")
            tl.update(item.id, "completed")
        assert tl.should_nudge_verification() is False

    def test_no_nudge_when_few_completed(self):
        tl = TodoList()
        item = tl.add("Task 1")
        tl.update(item.id, "completed")
        tl.add("Task 2")
        assert tl.should_nudge_verification() is False


class TestTodoListPersistence:
    """Save/load from disk."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_save_and_load(self):
        tl = TodoList(session_id="test_session")
        tl.add("Task A")
        item = tl.add("Task B")
        tl.update(item.id, "completed")
        tl.save(self.tmpdir)

        loaded = TodoList.load(self.tmpdir, "test_session")
        assert loaded is not None
        assert len(loaded.items) == 2
        assert loaded.items[1].status == "completed"

    def test_load_nonexistent(self):
        assert TodoList.load(self.tmpdir, "fake") is None

    def test_round_trip_preserves_timestamps(self):
        tl = TodoList(session_id="ts_test")
        item = tl.add("Timed task")
        tl.update(item.id, "completed")
        tl.save(self.tmpdir)

        loaded = TodoList.load(self.tmpdir, "ts_test")
        assert loaded.items[0].completed_at is not None
