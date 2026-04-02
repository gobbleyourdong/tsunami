"""Tests for active-project execution context."""

from pathlib import Path
import tempfile

from tsunami.agent import Agent
from tsunami.config import TsunamiConfig
from tsunami.tools.plan import get_agent_state
from tsunami.tools.project_init import _pick_scaffold
from tsunami.tools.python_exec import PythonExec


def test_agent_state_tracks_active_project_root():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = TsunamiConfig(workspace_dir=str(tmp / "workspace"), watcher_enabled=False)
        agent = Agent(cfg)
        project_dir = cfg.deliverables_dir / "demo-project"
        project_dir.mkdir(parents=True)
        (project_dir / "tsunami.md").write_text("# demo-project\n")

        agent.set_project("demo-project")

        state = get_agent_state()
        assert getattr(state, "active_project", "") == "demo-project"
        assert getattr(state, "active_project_root", "").endswith("/workspace/deliverables/demo-project")


def test_scaffold_picker_prefers_landing_for_splash_names():
    assert _pick_scaffold("custom-rack-splash", ["three", "react"]) == "landing"


async def _run_python_exec(tool: PythonExec):
    return await tool.execute(code="import os\nprint(os.getcwd())\nprint(sorted(os.listdir('.')))")  # noqa: E702


async def _run_python_exec_with_workspace_prefixed_path(tool: PythonExec):
    return await tool.execute(
        code=(
            "from pathlib import Path\n"
            "Path('./workspace/deliverables/demo-project/src/components').mkdir(parents=True, exist_ok=True)\n"
            "Path('./workspace/deliverables/demo-project/src/components/Test.txt').write_text('ok')\n"
            "print(Path('./src/components/Test.txt').read_text())\n"
        )
    )


async def _run_python_exec_with_repo_relative_path(tool: PythonExec):
    return await tool.execute(
        code=(
            "from pathlib import Path\n"
            "print(Path('./tsunami/context/tools.md').exists())\n"
        )
    )


def test_python_exec_runs_inside_active_project():
    import asyncio

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = TsunamiConfig(workspace_dir=str(tmp / "workspace"), watcher_enabled=False)
        agent = Agent(cfg)
        project_dir = cfg.deliverables_dir / "demo-project"
        src_dir = project_dir / "src"
        src_dir.mkdir(parents=True)
        (project_dir / "tsunami.md").write_text("# demo-project\n")
        (src_dir / "App.tsx").write_text("export default function App() {}\n")
        agent.set_project("demo-project")

        tool = PythonExec(cfg)
        result = asyncio.run(_run_python_exec(tool))

        assert not result.is_error
        assert str(project_dir) in result.content
        assert "src" in result.content


def test_python_exec_rewrites_workspace_prefixed_paths_to_active_project():
    import asyncio

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = TsunamiConfig(workspace_dir=str(tmp / "workspace"), watcher_enabled=False)
        agent = Agent(cfg)
        project_dir = cfg.deliverables_dir / "demo-project"
        project_dir.mkdir(parents=True)
        (project_dir / "tsunami.md").write_text("# demo-project\n")
        agent.set_project("demo-project")

        tool = PythonExec(cfg)
        result = asyncio.run(_run_python_exec_with_workspace_prefixed_path(tool))

        assert not result.is_error
        assert result.content.strip() == "ok"
        assert (project_dir / "src" / "components" / "Test.txt").read_text() == "ok"
        assert not (project_dir / "workspace").exists()


def test_python_exec_restores_process_cwd_after_execution():
    import asyncio
    import os

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = TsunamiConfig(workspace_dir=str(tmp / "workspace"), watcher_enabled=False)
        agent = Agent(cfg)
        project_dir = cfg.deliverables_dir / "demo-project"
        project_dir.mkdir(parents=True)
        (project_dir / "tsunami.md").write_text("# demo-project\n")
        agent.set_project("demo-project")

        tool = PythonExec(cfg)
        before = os.getcwd()
        result = asyncio.run(tool.execute(code="import os\nprint(os.getcwd())"))
        after = os.getcwd()

        assert not result.is_error
        assert str(project_dir) in result.content
        assert after == before


def test_python_exec_rewrites_repo_relative_paths_from_active_project():
    import asyncio

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = TsunamiConfig(workspace_dir=str(tmp / "workspace"), watcher_enabled=False)
        agent = Agent(cfg)
        project_dir = cfg.deliverables_dir / "demo-project"
        project_dir.mkdir(parents=True)
        (project_dir / "tsunami.md").write_text("# demo-project\n")
        agent.set_project("demo-project")

        tool = PythonExec(cfg)
        result = asyncio.run(_run_python_exec_with_repo_relative_path(tool))

        assert not result.is_error
        assert result.content.strip() == "True"
