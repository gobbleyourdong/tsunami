"""Tide build — wave decomposes an app, eddies write components in parallel.

The wave plans the architecture and specs each component.
Eddies write individual components as code strings (via done tool).
The wave assembles all components into the final files.

This solves the monolith problem: instead of the wave writing one
huge file, the work is parallelized across eddies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.tide_build")


class TideBuild(BaseTool):
    """Dispatch eddies to write app components in parallel, then assemble."""

    name = "tide_build"
    description = (
        "Build a multi-component app using parallel eddies. "
        "Provide a list of component specs — each eddy writes one component. "
        "Returns all component code for you to assemble into files. "
        "Use for apps with 3+ distinct parts (game engine, UI, styles, etc.)."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Component name (e.g. 'game-engine', 'ui-layer')"},
                            "spec": {"type": "string", "description": "Detailed spec for the eddy to implement"},
                            "language": {"type": "string", "description": "Output language (js, html, css, python)", "default": "javascript"},
                        },
                        "required": ["name", "spec"],
                    },
                    "description": "List of component specs to build in parallel",
                },
                "context": {
                    "type": "string",
                    "description": "Shared context all eddies need (e.g. data structures, API contracts)",
                    "default": "",
                },
            },
            "required": ["components"],
        }

    async def execute(self, components: list = None, context: str = "", **kwargs) -> ToolResult:
        if not components:
            return ToolResult("components list required", is_error=True)

        from ..eddy import run_swarm, format_swarm_results

        # Build task prompts for each eddy
        tasks = []
        for comp in components:
            name = comp.get("name", "unnamed")
            spec = comp.get("spec", "")
            lang = comp.get("language", "javascript")

            task = (
                f"Write the {name} component.\n\n"
                f"Language: {lang}\n"
            )
            if context:
                task += f"\nShared context:\n{context}\n"
            task += (
                f"\nSpec:\n{spec}\n\n"
                f"Output ONLY the code. No explanations. No markdown fences. "
                f"Just the raw code that goes in the file."
            )
            tasks.append(task)

        log.info(f"Tide build: dispatching {len(tasks)} eddies for components")

        # Run eddies in parallel
        workdir = str(Path(self.config.workspace_dir).parent)
        results = await run_swarm(
            tasks=tasks,
            workdir=workdir,
            max_concurrent=min(len(tasks), 8),
        )

        # Format results with component names
        lines = [f"tide_build: {len(results)} components built"]
        for i, (comp, r) in enumerate(zip(components, results)):
            name = comp.get("name", f"component_{i}")
            status = "ok" if r.success else "FAIL"
            lines.append(f"\n=== {name} [{status}] ===")
            if r.success and r.output:
                lines.append(r.output[:3000])
            elif r.error:
                lines.append(f"Error: {r.error}")

        succeeded = sum(1 for r in results if r.success)
        lines.append(f"\n{succeeded}/{len(results)} components built successfully.")
        lines.append("Use file_write to assemble these into the final files.")

        return ToolResult("\n".join(lines))
