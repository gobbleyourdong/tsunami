"""Toolbox loader — lazy-load tool groups on demand.

The agent starts with core tools + load_toolbox. When it needs
browser, webdev, or generation capabilities, it calls load_toolbox
to register those tools dynamically. File system as context.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.toolbox")

_registry = None


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


def _browser_tools():
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
    from .webdev import WebdevScaffold, WebdevServe, WebdevScreenshot, WebdevGenerateAssets
    return [WebdevScaffold, WebdevServe, WebdevScreenshot, WebdevGenerateAssets]

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

        tools = LOADERS[toolbox](self.config)
        loaded = []
        for tool in tools:
            if _registry.get(tool.name) is None:
                _registry.register(tool)
                loaded.append(tool.name)

        if not loaded:
            return ToolResult(f"Toolbox '{toolbox}' already loaded.")

        log.info(f"Loaded toolbox '{toolbox}': {loaded}")
        return ToolResult(f"Loaded: {', '.join(loaded)}")
