"""open_toolbox tool — drone's lazy-load handle for tool groups.

The drone sees a minimal set of "hand tools" always (file_read/write/edit,
shell_exec, message_result). Everything else is bundled into named
toolboxes. The drone calls open_toolbox('<name>') when it needs those
capabilities and the next iter's prompt carries their full schemas.

Registers as a tool the model can emit. Returns a short acknowledgement;
the real effect is on agent state — agent.py reads self._open_toolboxes
when building the next schema set.
"""

from __future__ import annotations

from .base import BaseTool, ToolResult


# Runtime state the agent references when building schemas. Reset per
# session in Agent.__init__.
_open_toolboxes: set[str] = set()


def get_open() -> set[str]:
    return set(_open_toolboxes)


def reset_open() -> None:
    _open_toolboxes.clear()


class OpenToolbox(BaseTool):
    name = "open_toolbox"
    description = (
        "Open a toolbox. Each toolbox bundles related tools; opening it "
        "loads those tools' full schemas into your next prompt. "
        "Available toolboxes: search, process, planning, assets, qa, scaffold."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "One of: search, process, planning, assets, qa, scaffold",
                },
            },
            "required": ["name"],
        }

    async def execute(self, name: str = "", **kw) -> ToolResult:
        from . import _TOOLBOXES
        if name not in _TOOLBOXES:
            return ToolResult(
                f"Unknown toolbox '{name}'. Available: "
                + ", ".join(sorted(_TOOLBOXES.keys())),
                is_error=True,
            )
        _open_toolboxes.add(name)
        tools = ", ".join(_TOOLBOXES[name])
        return ToolResult(
            f"Toolbox '{name}' open. Tools now available next turn: {tools}"
        )
