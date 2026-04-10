"""Swell tool — wave dispatches eddy workers that write files.

The wave decomposes a build into components. Each eddy writes one file.
The swell is the MoE router — file targets are the attention heads.
"""

from __future__ import annotations

import logging
import os

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.swell")

MAX_WORKERS = int(os.environ.get("TSUNAMI_MAX_WORKERS", "4"))


class Swell(BaseTool):
    """Dispatch parallel eddy workers. Each writes one file."""

    name = "swell"
    description = (
        f"Dispatch up to {MAX_WORKERS} parallel eddy workers. "
        "Each eddy gets a task prompt and a target file path. "
        "The eddy produces code, the swell writes it to the target file. "
        "Use for: writing multiple components in parallel. "
        "Give each eddy a focused task + the types/interfaces it needs. "
        "After swell completes, run shell_exec 'npx vite build' to compile-check."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "Task for the eddy — what code to write"},
                            "target": {"type": "string", "description": "File path to write the eddy's output to"},
                        },
                        "required": ["prompt", "target"],
                    },
                    "description": f"List of {{prompt, target}} tasks (max {MAX_WORKERS} concurrent).",
                },
            },
            "required": ["tasks"],
        }

    async def execute(self, tasks: list = None, **kwargs) -> ToolResult:
        if not tasks:
            return ToolResult("tasks list required", is_error=True)

        log.info(f"Swell: {len(tasks)} eddies")

        from ..eddy import run_swarm

        # Extract prompts and targets
        prompts = [t["prompt"] for t in tasks if "prompt" in t]
        targets = [t["target"] for t in tasks if "target" in t]

        if len(prompts) != len(targets):
            return ToolResult("Each task needs both 'prompt' and 'target'", is_error=True)

        # Use project root as workdir
        import os.path
        project_root = os.path.dirname(os.path.abspath(self.config.workspace_dir))

        # Try to find shared types for context
        types_context = ""
        for target in targets:
            from pathlib import Path as _P
            proj = _P(target).parent
            while proj != proj.parent:
                types_file = proj / "src" / "types.ts"
                if types_file.exists():
                    try:
                        types_context = f"\n\nShared types (import from '../types'):\n```\n{types_file.read_text()[:1500]}\n```"
                    except Exception:
                        pass
                    break
                proj = proj.parent

        results = await run_swarm(
            tasks=[p + types_context for p in prompts],
            workdir=project_root,
            max_concurrent=MAX_WORKERS,
            system_prompt=(
                "You are a TypeScript/React expert. "
                "Write a single component. Call done() with ONLY the raw TSX/TS code. "
                "No markdown fences. No explanation. Just the code. "
                "Import types from '../types' if provided. "
                "Export default function ComponentName."
            ),
            write_targets=targets,
        )

        # Format results
        lines = [f"Swell: {len(results)} eddies completed"]
        succeeded = 0
        for result, target in zip(results, targets):
            from pathlib import Path
            fname = Path(target).name
            exists = Path(target).exists()
            size = Path(target).stat().st_size if exists else 0
            ok = result.success and size > 0
            if ok:
                succeeded += 1
            lines.append(f"  {'✓' if ok else '✗'} {fname} ({size} bytes, {result.turns} turns)")

        lines.append(f"\n{succeeded}/{len(results)} files written successfully.")
        if succeeded < len(results):
            lines.append("Run the failed tasks individually or with the 9B wave for complex files.")

        return ToolResult("\n".join(lines))
