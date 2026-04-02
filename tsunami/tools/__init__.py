"""Tool registry — maps tool names to implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseTool, ToolResult

if TYPE_CHECKING:
    from ..config import TsunamiConfig


class ToolRegistry:
    """Central registry of all available tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def schemas(self) -> list[dict]:
        """Return all tool schemas in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema(),
                },
            }
            for t in self._tools.values()
        ]


def build_registry(config: TsunamiConfig) -> ToolRegistry:
    """Build the tool registry — bootstrap tools only.

    The agent starts with just enough to operate: messages, files, shell,
    search, planning, and load_toolbox. Everything else lives on disk in
    toolboxes/ — the agent reads those files to discover capabilities and
    calls load_toolbox to activate what it needs.
    """
    from .filesystem import FileRead, FileWrite, FileEdit, FileAppend
    from .match import MatchGlob, MatchGrep
    from .shell import ShellExec, ShellView
    from .message import MessageInfo, MessageAsk, MessageResult
    from .plan import PlanUpdate, PlanAdvance
    from .search import SearchWeb
    from .python_exec import PythonExec
    from .summarize import SummarizeFile
    from .swell import Swell
    from .undertow import Undertow
    from .project_init import ProjectInit
    from .generate import GenerateImage
    from .vision_ground import VisionGround
    from .toolbox import LoadToolbox, set_registry

    registry = ToolRegistry()

    # Bootstrap — lean core (18 tools)
    # generate_image + vision_ground in bootstrap — visual projects need them from the start
    for cls in [FileRead, FileWrite, FileEdit,
                MatchGlob, MatchGrep,
                ShellExec,
                MessageInfo, MessageAsk, MessageResult,
                PlanUpdate,
                SearchWeb, PythonExec, SummarizeFile, Swell, Undertow,
                ProjectInit, GenerateImage, VisionGround]:
        registry.register(cls(config))

    # The one meta-tool — loads everything else from disk
    registry.register(LoadToolbox(config))
    set_registry(registry)

    return registry
