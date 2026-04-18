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

Discovery (audit D22 restore — the fine-tune was trained to emit these
in every example's tool set):
  match_glob (find files by pattern)
  match_grep (regex search file contents)
  summarize_file (structural head+tail summary)

Deprecated (previously existed, now removed from codebase):
  swell, swell_build, swell_analyze, message_info, message_ask,
  python_exec, browser_*, webdev_*, load_toolbox, subtask_*, session_*.
  See git history commit where tools/ was trimmed for details.

Agent-side dispatching (not model-callable):
  Eddy swarm for multi-component writes: agent.py auto-detects missing
  component references and dispatches tsunami/eddy.py::run_swarm.
  Research parallelization: after first search_web, agent auto-dispatches
  per-result eddies to extract and merge. Neither is exposed to the model
  — the 4B is bad at deciding "fork 10 workers," the agent is good at it.
"""
from __future__ import annotations

from .base import BaseTool


#: qwen-code tool-name → tsunami tool-name aliases. The model was
#: trained on qwen-code's naming (read_file / write_file / edit /
#: run_shell_command / etc.), so when it emits those names we
#: transparently dispatch to our internal tools. The python classes
#: keep their tsunami names (file_read / file_write / file_edit /
#: shell_exec); the alias lookup happens on every get() call.
#:
#: Reference: QwenLM/qwen-code, packages/core/src/tools/tool-names.ts
_QWEN_TO_TSUNAMI_ALIAS: dict[str, str] = {
    "read_file":          "file_read",
    "write_file":         "file_write",
    "edit":               "file_edit",
    "run_shell_command":  "shell_exec",
    "web_search":         "search_web",
    # qwen-code names we intentionally leave unmapped:
    #   ask_user_question → message_ask (class exists but not in
    #       default registry — re-add the alias when/if message_ask
    #       is wired back in).
    #   glob / grep_search / list_directory / web_fetch / todo_write —
    #       no tsunami tools today. Add aliases when we land those.
}


class ToolRegistry:
    """Simple tool lookup by name. Supports qwen-code aliases so the
    model can emit its trained tool names (read_file, write_file,
    edit, run_shell_command) and land on our internal tools without
    renaming the python classes."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        # Direct hit first — our internal names take precedence so
        # existing callers (agent.py, tests, eval harnesses) that
        # use the tsunami spelling keep working.
        tool = self._tools.get(name)
        if tool is not None:
            return tool
        # Alias path: model emitted a qwen-code-native name. Log at
        # debug so repeated aliased calls don't spam; this is the
        # expected happy path post-R2.
        aliased = _QWEN_TO_TSUNAMI_ALIAS.get(name)
        if aliased is not None:
            return self._tools.get(aliased)
        return None

    def names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def tools(self) -> dict[str, BaseTool]:
        return self._tools

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]


def build_registry(config) -> ToolRegistry:
    """Build the 22-tool registry: core + planning + discovery + background-shell + append."""
    from .filesystem import FileRead, FileWrite, FileEdit, FileAppend
    from .shell import ShellExec, ShellView, ShellSend, ShellWait, ShellKill
    from .message import MessageResult, MessageChat
    from .search import SearchWeb
    from .undertow import Undertow
    from .riptide import Riptide
    from .project_init import ProjectInit
    from .generate import GenerateImage
    from .plan import PlanUpdate, PlanAdvance
    from .emit_design import EmitDesignTool
    # Audit D22 — the fine-tune was trained on these three in every example's
    # tool-declaration set; without them the model emits tool calls the
    # registry can't route, falling back to shell_exec "find"/"rg" for
    # capabilities that should be native.
    from .discovery import MatchGlob, MatchGrep, SummarizeFile

    registry = ToolRegistry()
    for cls in [
        FileRead, FileWrite, FileEdit, FileAppend,
        ShellExec, ShellView, ShellSend, ShellWait, ShellKill,
        MessageResult, MessageChat,
        SearchWeb,
        ProjectInit,
        Undertow, Riptide, GenerateImage,
        PlanUpdate, PlanAdvance,
        EmitDesignTool,
        MatchGlob, MatchGrep, SummarizeFile,
    ]:
        registry.register(cls(config))

    return registry
