"""Tests for single-project guardrails in the agent loop."""

from __future__ import annotations

import asyncio
import importlib.util
import tempfile

from tsunami.agent import Agent
from tsunami.config import TsunamiConfig
from tsunami.model import LLMModel, LLMResponse, ToolCall
from tsunami.tools import ToolRegistry
from tsunami.tools.base import BaseTool, ToolResult


class _ProjectInitModel(LLMModel):
    async def _call(self, messages, tools=None) -> LLMResponse:
        return LLMResponse(
            content="",
            tool_call=ToolCall(name="project_init", arguments={"name": "cat-grooming-biz"}),
        )


class _ExplodingProjectInit(BaseTool):
    name = "project_init"
    description = "Fake project init for testing."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        raise AssertionError("project_init should have been blocked by the active-project guard")


def test_blocks_second_project_init_when_project_already_active():
    tmpdir = tempfile.mkdtemp()
    cfg = TsunamiConfig(workspace_dir=tmpdir, watcher_enabled=False)
    agent = Agent(cfg)
    agent.model = _ProjectInitModel()

    registry = ToolRegistry()
    registry.register(_ExplodingProjectInit(cfg))
    agent.registry = registry

    active_dir = cfg.deliverables_dir / "dog-grooming-biz"
    active_dir.mkdir(parents=True)
    (active_dir / "tsunami.md").write_text("# dog-grooming-biz\n")
    agent.set_project("dog-grooming-biz")

    agent.state.add_system("system")
    agent.state.add_user("create a dog grooming biz landing page")

    result = asyncio.run(agent._step())

    assert "Do not create 'cat-grooming-biz'" in result
    assert "dog-grooming-biz" in result
    assert agent.active_project == "dog-grooming-biz"

    last = agent.state.conversation[-1]
    assert last.role == "tool_result"
    assert "[project_init] ERROR:" in last.content
    assert "Continue working in ./workspace/deliverables/dog-grooming-biz/" in last.content


class _SuccessfulProjectInit(BaseTool):
    name = "project_init"
    description = "Fake project init for testing."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }

    async def execute(self, name: str = "", **kwargs) -> ToolResult:
        project_dir = self.config.deliverables_dir / name
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "tsunami.md").write_text(f"# {name}\n")
        return ToolResult(f"Project '{name}' ready")


def test_project_init_preloads_web_toolboxes():
    tmpdir = tempfile.mkdtemp()
    cfg = TsunamiConfig(workspace_dir=tmpdir, watcher_enabled=False)
    agent = Agent(cfg)
    agent.model = _ProjectInitModel()

    registry = ToolRegistry()
    registry.register(_SuccessfulProjectInit(cfg))
    agent.registry = registry

    agent.state.add_system("system")
    agent.state.add_user("create a landing page")

    result = asyncio.run(agent._step())

    assert "Preloaded tools for this project:" in result
    assert agent.registry.get("webdev_serve") is not None
    if importlib.util.find_spec("playwright") is not None:
        assert agent.registry.get("browser_navigate") is not None
        assert agent.registry.get("webdev_screenshot") is not None
    else:
        assert agent.registry.get("browser_navigate") is None
        assert agent.registry.get("webdev_screenshot") is None


class _ExplodingWebdevScaffold(BaseTool):
    name = "webdev_scaffold"
    description = "Fake scaffold for testing."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"project_name": {"type": "string"}},
            "required": ["project_name"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        raise AssertionError("webdev_scaffold should have been blocked by the active-project guard")


def test_blocks_second_webdev_scaffold_when_project_already_active():
    tmpdir = tempfile.mkdtemp()
    cfg = TsunamiConfig(workspace_dir=tmpdir, watcher_enabled=False)
    agent = Agent(cfg)
    agent.model = _ProjectInitModel()

    registry = ToolRegistry()
    registry.register(_ExplodingWebdevScaffold(cfg))
    agent.registry = registry

    active_dir = cfg.deliverables_dir / "dog-grooming-biz"
    active_dir.mkdir(parents=True)
    (active_dir / "tsunami.md").write_text("# dog-grooming-biz\n")
    agent.set_project("dog-grooming-biz")

    result = agent._maybe_redirect_active_project_setup(
        ToolCall(name="webdev_scaffold", arguments={"project_name": "dog-grooming-biz"})
    )

    assert result is not None
    assert "do not scaffold it again" in result.content
    assert "edit src/App.tsx" in result.content
