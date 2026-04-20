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
  generate_image (create reference via ERNIE-Image-Turbo)

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

    def schemas(self, open_toolboxes: list[str] | None = None) -> list[dict]:
        """Return tool schemas for what's exposed to the model right now.

        When `open_toolboxes` is None → all tools (legacy behavior).
        When `open_toolboxes` is a list → always-available tools plus
        tools from the named toolboxes. Lets the agent reduce per-iter
        tool-schema prefill from ~3300 → ~1500 tokens on typical edits
        by only surfacing toolboxes currently relevant to the task.
        """
        if open_toolboxes is None:
            return [t.schema() for n, t in self._tools.items()
                    if n not in _WAVE_ONLY_TOOLS]
        allowed: set[str] = set(_ALWAYS_TOOLS)
        for name in open_toolboxes:
            allowed.update(_TOOLBOXES.get(name, ()))
        # Wave-only tools are never in any drone schema, even if a phase
        # toolbox happens to include them. Treat the wave-only list as
        # the authoritative floor.
        allowed -= _WAVE_ONLY_TOOLS
        return [t.schema() for n, t in self._tools.items() if n in allowed]


# Always-loaded tools — the drone's "hand tools" that fit every edit
# iteration regardless of phase. Wave injects more via phase→toolbox
# mapping (see _PHASE_TOOLBOXES below).
_ALWAYS_TOOLS: tuple[str, ...] = (
    "file_write", "file_edit",
    "message_result",
    # Minimal hand-tools. Drones working a scaffold need to change files
    # and deliver — that's it. Everything else (file_read, shell_exec,
    # match_grep) was letting the drone spiral on exploration/diagnosis
    # when the wave already inlined the scaffold params, test source, and
    # App.tsx stub into the system prompt. On build fail, the wave
    # re-emits with the compile errors; drone rewrites. No reads needed.
    # file_read returns via the "read" toolbox when a FIX/DIAGNOSE phase
    # explicitly opens it.
)


# Wave-only tools — the orchestrator invokes these directly via
# registry.get(). They never appear in any drone-facing schema. Putting
# them here instead of in drone toolboxes is a strict allowlist: the
# drone simply cannot see or emit them, no filtering needed.
_WAVE_ONLY_TOOLS: frozenset[str] = frozenset({
    "project_init",    # pre_scaffold invokes this
    "project_init_gamedev",  # gamedev variant — wave-fired for genre scaffolds
    "riptide",         # grounding gate uses for bbox extraction
    "undertow",        # delivery gate uses for QA
    "plan_update",     # wave maintains plan.md
    "plan_advance",    # wave transitions plan sections
    # emit_design and generate_image NOT wave-only — drones need them:
    # generate_image for art/hero/sprite content, emit_design for
    # gamedev. Wave uses them too (grounding gate) but drone visibility
    # is the common case. search_web also drone-facing now for reference
    # image pulls during build (not just grounding).
})

# Toolbox layout. Each toolbox name maps to a tuple of tool names.
#
# Tools are solitons — a single registered instance per name. Toolboxes
# are VIEWS into that registry. A tool can appear in multiple toolboxes
# without duplication; the schemas() set-union resolves membership
# automatically. Example: `undertow` lives in `qa` (delivery QA) AND
# `assets` (visual sanity check on generated content); `summarize_file`
# lives in `search` (find things) AND `scaffold` (learn the layout).
#
# Rule of thumb: put a tool wherever a drone might reach for it in
# context. The cost of multi-membership is zero (shared reference); the
# cost of under-scoped membership is a drone that can't find the tool.
_TOOLBOXES: dict[str, tuple[str, ...]] = {
    "search":   ("match_glob", "match_grep", "summarize_file", "search_web"),
    "process":  ("shell_view", "shell_send", "shell_wait", "shell_kill"),
    "planning": ("plan_update", "plan_advance", "emit_design"),
    "assets":   ("generate_image", "edit_image", "riptide", "undertow"),
    "qa":       ("undertow", "message_chat"),
    "scaffold": ("project_init", "project_init_gamedev", "file_append", "summarize_file"),
}


def list_toolboxes() -> dict[str, tuple[str, ...]]:
    return dict(_TOOLBOXES)


# Phase → toolbox distribution. The orchestrator (wave) reads the
# current plan phase and hands the drone the tools that phase needs.
# Drone never opens toolboxes itself — it's a pure function from
# (context, tools) → action. The wave can override per-drone (e.g.
# parallel drones on the same project can get different surfaces).
_PHASE_TOOLBOXES: dict[str, tuple[str, ...]] = {
    "SCAFFOLD": ("scaffold",),                     # project_init, file_append
    "WRITE":    (),                                # always-tools are enough
    "TEST":     (),
    "FIX":      (),
    "BUILD":    (),
    "DELIVER":  ("qa",),                           # undertow, message_chat
    "POLISH":   ("assets", "qa"),                  # generate_image, riptide, undertow
    "RESEARCH": ("search",),                       # match_glob/grep/summarize, search_web
    "REPLAN":   ("planning",),                     # plan_update/advance/emit_design
}


def toolboxes_for_phase(phase: str) -> list[str]:
    """Return toolbox names the wave opens for the drone in `phase`.
    Unknown phases get an empty set (always-tools only).
    """
    return list(_PHASE_TOOLBOXES.get(phase, ()))


def build_registry(config) -> ToolRegistry:
    """Build the 22-tool registry: core + planning + discovery + background-shell + append."""
    from .filesystem import FileRead, FileWrite, FileEdit, FileAppend
    from .shell import ShellExec, ShellView, ShellSend, ShellWait, ShellKill
    from .message import MessageResult, MessageChat
    from .search import SearchWeb
    from .undertow import Undertow
    from .riptide import Riptide
    from .project_init import ProjectInit
    from .project_init_gamedev import ProjectInitGamedev
    from .generate import GenerateImage, EditImage
    from .plan import PlanUpdate, PlanAdvance
    from .emit_design import EmitDesignTool
    # Audit D22 — the fine-tune was trained on these three in every example's
    # tool-declaration set; without them the model emits tool calls the
    # registry can't route, falling back to shell_exec "find"/"rg" for
    # capabilities that should be native.
    from .discovery import MatchGlob, MatchGrep, SummarizeFile

    # open_toolbox deliberately NOT registered — the wave owns toolbox
    # distribution (phase_machine.phase → toolboxes_for_phase → schemas).
    # Drone is a pure function, not a tool-surface manager.

    registry = ToolRegistry()
    for cls in [
        FileRead, FileWrite, FileEdit, FileAppend,
        ShellExec, ShellView, ShellSend, ShellWait, ShellKill,
        MessageResult, MessageChat,
        SearchWeb,
        ProjectInit,
        ProjectInitGamedev,
        Undertow, Riptide, GenerateImage, EditImage,
        PlanUpdate, PlanAdvance,
        EmitDesignTool,
        MatchGlob, MatchGrep, SummarizeFile,
    ]:
        registry.register(cls(config))

    return registry
