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


def build_registry(config: TsunamiConfig, profile: str = "full") -> ToolRegistry:
    """Build a tool registry from config.

    Profiles control which tools are loaded to save context tokens:
      - "core": 16 tools (~1800 tokens) — file, shell, match, message, plan, search
      - "full": 35 tools (~3681 tokens) — everything including browser, generate, etc.
    """
    from .filesystem import FileRead, FileWrite, FileEdit, FileAppend
    from .match import MatchGlob, MatchGrep
    from .shell import ShellExec, ShellView, ShellSend, ShellWait, ShellKill
    from .message import MessageInfo, MessageAsk, MessageResult
    from .plan import PlanUpdate, PlanAdvance
    from .search import SearchWeb

    registry = ToolRegistry()

    # === Core tools (always loaded) ===
    for tool_cls in [FileRead, FileWrite, FileEdit, FileAppend]:
        registry.register(tool_cls(config))

    for tool_cls in [MatchGlob, MatchGrep]:
        registry.register(tool_cls(config))

    for tool_cls in [ShellExec, ShellView, ShellSend, ShellWait, ShellKill]:
        registry.register(tool_cls(config))

    for tool_cls in [MessageInfo, MessageAsk, MessageResult]:
        registry.register(tool_cls(config))

    for tool_cls in [PlanUpdate, PlanAdvance]:
        registry.register(tool_cls(config))

    registry.register(SearchWeb(config))

    # === Extended tools (full profile only) ===
    if profile == "full":
        from .browser import (
            BrowserNavigate, BrowserView, BrowserClick, BrowserInput,
            BrowserScroll, BrowserFindKeyword, BrowserConsoleExec,
            BrowserFillForm, BrowserPressKey, BrowserSelectOption,
            BrowserSaveImage, BrowserUploadFile, BrowserClose,
        )
        from .map_tool import MapTool
        from .creation import FileView, ExposeTool, ScheduleTool
        from .generate import GenerateImage

        registry.register(FileView(config))

        for tool_cls in [BrowserNavigate, BrowserView, BrowserClick, BrowserInput,
                         BrowserScroll, BrowserFindKeyword, BrowserConsoleExec,
                         BrowserFillForm, BrowserPressKey, BrowserSelectOption,
                         BrowserSaveImage, BrowserUploadFile, BrowserClose]:
            registry.register(tool_cls(config))

        registry.register(MapTool(config))
        registry.register(ExposeTool(config))
        registry.register(ScheduleTool(config))
        registry.register(GenerateImage(config))

        # Web development tools
        from .webdev import WebdevScaffold, WebdevServe, WebdevScreenshot, WebdevGenerateAssets
        for tool_cls in [WebdevScaffold, WebdevServe, WebdevScreenshot, WebdevGenerateAssets]:
            registry.register(tool_cls(config))

    return registry
