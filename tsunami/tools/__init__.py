"""Tool registry — 11 tools, one mode.

Previous design had separate "lite" (2B/4B) and "full" (9B+) registries.
That split is gone — there's only one model target (Gemma 4 E4B) and one
tool surface. Any agent sees these 11 tools, no branching.

Core pipeline (saturated in training):
  project_init, file_write, file_edit, file_read, shell_exec,
  undertow, message_result

Conversational:
  message_chat (done=true ends, done=false continues)

Research:
  search_web

Vision (force multiplier for small models):
  riptide (extract element positions from a reference image)
  generate_image (create reference via Z-Image-Turbo)

Deprecated (previously existed, now removed from codebase):
  plan_update, plan_advance, swell, swell_build, swell_analyze,
  message_info, message_ask, match_glob, match_grep, python_exec,
  summarize_file, browser_*, webdev_*, load_toolbox, subtask_*,
  session_*. See git history commit where tools/ was trimmed for details.

Agent-side dispatching (not model-callable):
  Eddy swarm for multi-component writes: agent.py auto-detects missing
  component references and dispatches tsunami/eddy.py::run_swarm.
  Research parallelization: after first search_web, agent auto-dispatches
  per-result eddies to extract and merge. Neither is exposed to the model
  — the 4B is bad at deciding "fork 10 workers," the agent is good at it.
"""
from __future__ import annotations

from .base import BaseTool


class ToolRegistry:
    """Simple tool lookup by name."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def tools(self) -> dict[str, BaseTool]:
        return self._tools

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]


def build_registry(config) -> ToolRegistry:
    """Build the one-and-only 11-tool registry."""
    from .filesystem import FileRead, FileWrite, FileEdit
    from .shell import ShellExec
    from .message import MessageResult, MessageChat
    from .search import SearchWeb
    from .undertow import Undertow
    from .riptide import Riptide
    from .project_init import ProjectInit
    from .generate import GenerateImage

    registry = ToolRegistry()
    for cls in [
        FileRead, FileWrite, FileEdit,
        ShellExec,
        MessageResult, MessageChat,
        SearchWeb,
        ProjectInit,
        Undertow, Riptide, GenerateImage,
    ]:
        registry.register(cls(config))

    return registry
