"""Toolbox loader — lazy-load tool groups on demand.

The agent starts with core tools + load_toolbox. When it needs
browser, webdev, or generation capabilities, it calls load_toolbox
to register those tools dynamically. File system as context.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.toolbox")

_registry = None


def _playwright_available() -> bool:
    return importlib.util.find_spec("playwright") is not None


def set_registry(registry):
    global _registry
    _registry = registry


LOADERS = {
    "browser": lambda config: [cls(config) for cls in _browser_tools()],
    "webdev": lambda config: [cls(config) for cls in _webdev_tools()],
    "generate": lambda config: [cls(config) for cls in _generate_tools()],
    "services": lambda config: [cls(config) for cls in _service_tools()],
    "parallel": lambda config: [cls(config) for cls in _parallel_tools()],
    "management": lambda config: [cls(config) for cls in _management_tools()],
}


def load_toolbox_into_registry(registry, config, toolbox: str) -> list[str]:
    """Register a toolbox into a registry and return the newly loaded tool names."""
    if toolbox not in LOADERS:
        raise KeyError(toolbox)

    tools = LOADERS[toolbox](config)
    loaded: list[str] = []
    for tool in tools:
        if registry.get(tool.name) is None:
            registry.register(tool)
            loaded.append(tool.name)
    return loaded


def _browser_tools():
    if not _playwright_available():
        return []
    from .browser import (
        BrowserNavigate, BrowserView, BrowserClick, BrowserInput,
        BrowserScroll, BrowserFindKeyword, BrowserConsoleExec,
        BrowserFillForm, BrowserPressKey, BrowserSelectOption,
        BrowserSaveImage, BrowserUploadFile, BrowserClose,
    )
    return [BrowserNavigate, BrowserView, BrowserClick, BrowserInput,
            BrowserScroll, BrowserFindKeyword, BrowserConsoleExec,
            BrowserFillForm, BrowserPressKey, BrowserSelectOption,
            BrowserSaveImage, BrowserUploadFile, BrowserClose]

def _webdev_tools():
    from .webdev import WebdevScaffold, WebdevServe, WebdevGenerateAssets
    tools = [WebdevScaffold, WebdevServe, WebdevGenerateAssets]
    if _playwright_available():
        from .webdev import WebdevScreenshot
        tools.append(WebdevScreenshot)
    return tools

def _generate_tools():
    from .generate import GenerateImage
    return [GenerateImage]

def _service_tools():
    from .creation import FileView, ExposeTool, ScheduleTool
    return [FileView, ExposeTool, ScheduleTool]

def _parallel_tools():
    from .map_tool import MapTool
    return [MapTool]

def _management_tools():
    from .subtask import SubtaskCreate, SubtaskDone
    from .session_tools import SessionList, SessionSummary
    from .shell import ShellSend, ShellWait, ShellKill
    return [SubtaskCreate, SubtaskDone, SessionList, SessionSummary, ShellSend, ShellWait, ShellKill]


class LoadToolbox(BaseTool):
    name = "load_toolbox"
    description = (
        "Load tools on demand. Available: "
        "browser (navigate/click/screenshot 13 tools), "
        "webdev (scaffold/serve/screenshot 4 tools), "
        "generate (image gen 1 tool), "
        "services (expose/schedule 3 tools), "
        "parallel (batch map 1 tool), "
        "management (subtasks/sessions/shell 7 tools)"
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "toolbox": {
                    "type": "string",
                    "description": "Toolbox to load: browser, webdev, generate, services, parallel",
                },
            },
        }

    async def execute(self, toolbox: str = "", **kwargs) -> ToolResult:
        if not toolbox or toolbox not in LOADERS:
            readme = Path(__file__).parent.parent.parent / "toolboxes" / "README.md"
            if readme.exists():
                return ToolResult(readme.read_text())
            return ToolResult(f"Available: {', '.join(LOADERS.keys())}")

        if _registry is None:
            return ToolResult("Registry not initialized", is_error=True)

        loaded = load_toolbox_into_registry(_registry, self.config, toolbox)

        if not loaded:
            return ToolResult(f"Toolbox '{toolbox}' already loaded.")

        log.info(f"Loaded toolbox '{toolbox}': {loaded}")
        return ToolResult(f"Loaded: {', '.join(loaded)}")
