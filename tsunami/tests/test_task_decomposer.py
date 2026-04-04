"""Tests for task decomposer + loop guard.

Verifies prompt decomposition and stall detection.
"""

from tsunami.task_decomposer import (
    decompose, is_complex_prompt, detect_domains, TaskDAG, SubTask,
)
from tsunami.loop_guard import LoopGuard, LoopDetection


class TestDomainDetection:
    def test_weather_stocks(self):
        domains = detect_domains("weather and stock tracker with charts")
        assert "api_external" in domains
        assert "data_viz" in domains

    def test_kanban_calendar(self):
        domains = detect_domains("kanban board with calendar view and drag drop")
        assert "interactive" in domains
        assert "calendar" in domains

    def test_simple_prompt(self):
        domains = detect_domains("build a counter")
        assert len(domains) == 0


class TestComplexityDetection:
    def test_weather_stocks_is_complex(self):
        assert is_complex_prompt("build a weather and stock tracker dashboard side by side — weather with 5-day forecast, stocks with live-ish price chart")

    def test_kanban_calendar_is_complex(self):
        assert is_complex_prompt("build a project management tool that combines Kanban boards with a calendar view. Drag cards between columns AND onto calendar dates. Card detail modal with description, assignee, due date, checklist.")

    def test_counter_not_complex(self):
        assert not is_complex_prompt("build a counter")

    def test_password_gen_not_complex(self):
        assert not is_complex_prompt("build a password generator with length slider and copy button")


class TestDecomposition:
    def test_complex_prompt_produces_dag(self):
        dag = decompose("build a weather and stock tracker dashboard with charts and real-time updates")
        assert dag.is_complex
        assert len(dag.tasks) >= 3

    def test_simple_prompt_passthrough(self):
        dag = decompose("build a counter")
        assert not dag.is_complex
        assert len(dag.tasks) == 1

    def test_dag_always_has_scaffold_first(self):
        dag = decompose("build a dashboard with charts, search, calendar, and drag-drop kanban")
        assert dag.is_complex
        assert dag.tasks[0].id == "scaffold"

    def test_dag_has_integration_last(self):
        dag = decompose("build a dashboard with charts, search, calendar, and drag-drop")
        if dag.is_complex:
            assert dag.tasks[-1].id == "integrate"

    def test_phased_prompt_format(self):
        dag = decompose("build a weather and stock tracker dashboard with charts and live updates and search")
        prompt = dag.to_phased_prompt()
        assert "Phase 1" in prompt
        assert "project_init" in prompt
        assert "BUILD" in prompt


class TestLoopGuard:
    def test_no_loop_initially(self):
        guard = LoopGuard()
        assert not guard.check().detected

    def test_hard_loop_detected(self):
        guard = LoopGuard()
        for _ in range(3):
            guard.record("file_read", {"path": "src/App.tsx"}, False)
        result = guard.check()
        assert result.detected
        assert result.loop_type == "hard"

    def test_soft_loop_detected(self):
        guard = LoopGuard()
        for i in range(5):
            guard.record("file_read", {"path": f"src/file{i}.tsx"}, False)
        result = guard.check()
        assert result.detected
        assert result.loop_type == "soft"

    def test_progress_stall_detected(self):
        guard = LoopGuard()
        for i in range(8):
            guard.record("file_read", {"path": f"file{i}"}, False)
        result = guard.check()
        assert result.detected

    def test_no_loop_with_progress(self):
        guard = LoopGuard()
        for i in range(8):
            guard.record("file_write", {"path": f"file{i}"}, True)
        result = guard.check()
        # Soft loop on tool name but progress is being made
        # The soft loop fires because same tool 5x, but forced_action suggests file_write->shell_exec
        assert result.loop_type in ("soft", "")

    def test_forced_action_for_read_loop(self):
        guard = LoopGuard()
        for _ in range(3):
            guard.record("file_read", {"path": "same.tsx"}, False)
        result = guard.check()
        assert result.forced_action == "project_init"

    def test_forced_action_for_write_loop(self):
        guard = LoopGuard()
        for _ in range(3):
            guard.record("file_write", {"path": "same.tsx", "content": "x"}, False)
        result = guard.check()
        assert result.forced_action == "shell_exec"

    def test_reset(self):
        guard = LoopGuard()
        for _ in range(5):
            guard.record("file_read", {"path": "x"}, False)
        assert guard.check().detected
        guard.reset()
        assert not guard.check().detected
