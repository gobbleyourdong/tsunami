"""Tests for conversation forking."""

import json
import os
import tempfile
import pytest

from tsunami.state import AgentState, Message, Plan, Phase
from tsunami.fork import (
    create_fork,
    restore_fork,
    list_forks,
    derive_title,
    _unique_fork_name,
)


class TestDeriveTitle:
    """Fork title derivation from first user message."""

    def test_simple_message(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("Fix the login bug")
        assert derive_title(state) == "Fix the login bug"

    def test_multiline_collapsed(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("Fix the\n  login\n  bug")
        assert derive_title(state) == "Fix the login bug"

    def test_truncated_at_100(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("x" * 200)
        assert len(derive_title(state)) == 100

    def test_no_user_message(self):
        state = AgentState()
        state.add_system("sys")
        assert derive_title(state) == "Branched conversation"

    def test_empty_user_message(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("")
        assert derive_title(state) == "Branched conversation"

    def test_whitespace_only(self):
        state = AgentState()
        state.add_system("sys")
        state.add_user("   \n\t  ")
        assert derive_title(state) == "Branched conversation"


class TestCreateFork:
    """Fork creation — snapshot conversation to disk."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _build_state(self) -> AgentState:
        state = AgentState(workspace_dir=self.tmpdir)
        state.add_system("System prompt")
        state.add_user("Do something important")
        state.add_assistant("I'll help", tool_call={"function": {"name": "file_read", "arguments": {}}})
        state.conversation.append(Message(role="tool_result", content="[file_read] contents"))
        state.iteration = 5
        return state

    def test_creates_fork_file(self):
        state = self._build_state()
        fork_id = create_fork(state, self.tmpdir)
        fork_file = os.path.join(self.tmpdir, ".forks", f"{fork_id}.json")
        assert os.path.exists(fork_file)

    def test_fork_contains_all_messages(self):
        state = self._build_state()
        fork_id = create_fork(state, self.tmpdir)
        fork_file = os.path.join(self.tmpdir, ".forks", f"{fork_id}.json")
        data = json.loads(open(fork_file).read())
        assert len(data["messages"]) == 4

    def test_fork_preserves_metadata(self):
        state = self._build_state()
        fork_id = create_fork(state, self.tmpdir)
        fork_file = os.path.join(self.tmpdir, ".forks", f"{fork_id}.json")
        data = json.loads(open(fork_file).read())
        assert data["iteration"] == 5
        assert data["fork_id"] == fork_id

    def test_custom_name(self):
        state = self._build_state()
        fork_id = create_fork(state, self.tmpdir, fork_name="My checkpoint")
        fork_file = os.path.join(self.tmpdir, ".forks", f"{fork_id}.json")
        data = json.loads(open(fork_file).read())
        assert "My checkpoint" in data["title"]

    def test_preserves_plan(self):
        state = self._build_state()
        state.plan = Plan(
            goal="Fix everything",
            phases=[Phase(id=1, title="Phase 1", status="active")],
        )
        fork_id = create_fork(state, self.tmpdir)
        fork_file = os.path.join(self.tmpdir, ".forks", f"{fork_id}.json")
        data = json.loads(open(fork_file).read())
        assert data["plan"]["goal"] == "Fix everything"


class TestRestoreFork:
    """Fork restoration — load conversation from disk."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_round_trip(self):
        """Create fork → restore → same conversation."""
        state = AgentState(workspace_dir=self.tmpdir)
        state.add_system("sys")
        state.add_user("usr")
        state.add_assistant("ast")
        state.iteration = 7

        fork_id = create_fork(state, self.tmpdir)
        restored = restore_fork(fork_id, self.tmpdir)

        assert restored is not None
        assert len(restored.conversation) == 3
        assert restored.conversation[0].role == "system"
        assert restored.conversation[1].role == "user"
        assert restored.iteration == 7

    def test_restores_tool_calls(self):
        state = AgentState(workspace_dir=self.tmpdir)
        state.add_system("sys")
        state.add_user("usr")
        state.add_assistant("call", tool_call={"function": {"name": "test", "arguments": {"x": 1}}})

        fork_id = create_fork(state, self.tmpdir)
        restored = restore_fork(fork_id, self.tmpdir)

        assert restored.conversation[2].tool_call is not None
        assert restored.conversation[2].tool_call["function"]["name"] == "test"

    def test_restores_plan(self):
        state = AgentState(workspace_dir=self.tmpdir)
        state.add_system("sys")
        state.add_user("usr")
        state.plan = Plan(goal="test", phases=[Phase(id=1, title="p1", status="complete")])

        fork_id = create_fork(state, self.tmpdir)
        restored = restore_fork(fork_id, self.tmpdir)

        assert restored.plan is not None
        assert restored.plan.goal == "test"
        assert restored.plan.phases[0].status == "complete"

    def test_nonexistent_fork(self):
        result = restore_fork("fork_nonexistent", self.tmpdir)
        assert result is None


class TestListForks:
    """Fork listing."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_empty(self):
        assert list_forks(self.tmpdir) == []

    def test_lists_created_forks(self):
        import time
        state1 = AgentState(workspace_dir=self.tmpdir)
        state1.add_system("sys")
        state1.add_user("First task")
        create_fork(state1, self.tmpdir, fork_name="fork-A")

        time.sleep(0.002)  # ensure different millisecond timestamp

        state2 = AgentState(workspace_dir=self.tmpdir)
        state2.add_system("sys")
        state2.add_user("Second task")
        create_fork(state2, self.tmpdir, fork_name="fork-B")

        forks = list_forks(self.tmpdir)
        assert len(forks) == 2
        assert all("fork_id" in f for f in forks)
        assert all("title" in f for f in forks)


class TestUniqueForkName:
    """Fork name collision avoidance."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, ".forks"), exist_ok=True)
        self.forks_dir = os.path.join(self.tmpdir, ".forks")

    def _create_fake_fork(self, title: str):
        import time
        fork_id = f"fork_{int(time.time() * 1000)}"
        data = {"fork_id": fork_id, "title": title, "messages": []}
        with open(os.path.join(self.forks_dir, f"{fork_id}.json"), "w") as f:
            json.dump(data, f)
        import time as t; t.sleep(0.002)  # ensure unique timestamps

    def test_first_fork_gets_branch_suffix(self):
        from pathlib import Path
        name = _unique_fork_name(Path(self.forks_dir), "My task")
        assert name == "My task (Branch)"

    def test_collision_gets_number(self):
        from pathlib import Path
        self._create_fake_fork("My task (Branch)")
        name = _unique_fork_name(Path(self.forks_dir), "My task")
        assert name == "My task (Branch 2)"

    def test_multiple_collisions(self):
        from pathlib import Path
        self._create_fake_fork("My task (Branch)")
        self._create_fake_fork("My task (Branch 2)")
        name = _unique_fork_name(Path(self.forks_dir), "My task")
        assert name == "My task (Branch 3)"
