"""Tests for active-project path rewriting and scaffold choice."""

from pathlib import Path

from tsunami.agent import Agent
from tsunami.config import TsunamiConfig
from tsunami.model import ToolCall
from tsunami.tools.project_init import _pick_scaffold


def _agent_with_project(tmp_path: Path) -> Agent:
    cfg = TsunamiConfig(workspace_dir=str(tmp_path / "workspace"), watcher_enabled=False)
    agent = Agent(cfg)
    project_dir = cfg.deliverables_dir / "demo-project"
    project_dir.mkdir(parents=True)
    (project_dir / "tsunami.md").write_text("# demo-project\n")
    agent.set_project("demo-project")
    return agent


def test_rewrites_match_directory_into_active_project(tmp_path):
    agent = _agent_with_project(tmp_path)
    tool_call = ToolCall(name="match_glob", arguments={"pattern": "**/*.ts", "directory": "src/components"})

    normalized = agent._normalize_project_local_args(tool_call)

    assert normalized.arguments["directory"].endswith("/workspace/deliverables/demo-project/src/components")


def test_rewrites_file_path_into_active_project(tmp_path):
    agent = _agent_with_project(tmp_path)
    tool_call = ToolCall(name="file_read", arguments={"path": "src/App.tsx"})

    normalized = agent._normalize_project_local_args(tool_call)

    assert normalized.arguments["path"].endswith("/workspace/deliverables/demo-project/src/App.tsx")


def test_does_not_rewrite_explicit_workspace_path(tmp_path):
    agent = _agent_with_project(tmp_path)
    tool_call = ToolCall(
        name="match_glob",
        arguments={"pattern": "**/*.ts", "directory": "./workspace/deliverables/demo-project/src"},
    )

    normalized = agent._normalize_project_local_args(tool_call)

    assert normalized.arguments["directory"] == "./workspace/deliverables/demo-project/src"


def test_rewrites_cross_project_workspace_path_to_active_project(tmp_path):
    agent = _agent_with_project(tmp_path)
    tool_call = ToolCall(
        name="file_read",
        arguments={"path": "./workspace/deliverables/other-project/src/App.tsx"},
    )

    normalized = agent._normalize_project_local_args(tool_call)

    assert normalized.arguments["path"] == "./workspace/deliverables/demo-project/src/App.tsx"


def test_rewrites_cross_project_command_to_active_project(tmp_path):
    agent = _agent_with_project(tmp_path)
    tool_call = ToolCall(
        name="shell_exec",
        arguments={"command": "cd ./workspace/deliverables/other-project && npm run build"},
    )

    normalized = agent._normalize_project_local_args(tool_call)

    assert normalized.arguments["command"] == "cd ./workspace/deliverables/demo-project && npm run build"


def test_rewrites_cross_project_python_code_to_active_project(tmp_path):
    agent = _agent_with_project(tmp_path)
    tool_call = ToolCall(
        name="python_exec",
        arguments={"code": "with open('./workspace/deliverables/other-project/src/App.tsx') as f:\n    print(f.read())"},
    )

    normalized = agent._normalize_project_local_args(tool_call)

    assert "./workspace/deliverables/demo-project/src/App.tsx" in normalized.arguments["code"]
    assert "other-project" not in normalized.arguments["code"]


def test_scopes_broad_match_search_to_active_project_by_default(tmp_path):
    agent = _agent_with_project(tmp_path)
    tool_call = ToolCall(
        name="match_glob",
        arguments={"pattern": "**/*", "directory": "."},
    )

    normalized = agent._normalize_project_local_args(tool_call)

    assert normalized.arguments["directory"].endswith("/workspace/deliverables/demo-project")


def test_keeps_repo_wide_match_search_when_pattern_targets_repo_files(tmp_path):
    agent = _agent_with_project(tmp_path)
    tool_call = ToolCall(
        name="match_glob",
        arguments={"pattern": "**/*.md", "directory": "."},
    )

    normalized = agent._normalize_project_local_args(tool_call)

    assert normalized.arguments["directory"] == "."


def test_three_dependency_alone_does_not_force_game_scaffold():
    assert _pick_scaffold("custom-rack-builds", ["three", "react", "react-dom"]) == "react-app"


def test_game_scaffold_still_selected_for_real_game_signal():
    assert _pick_scaffold("pinball-arena", ["three", "rapier"]) == "threejs-game"
