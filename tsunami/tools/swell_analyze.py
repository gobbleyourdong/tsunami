"""Swell analyze — batch-analyze files via parallel eddy workers.

When given a directory of files and a question, dispatches eddy workers
that can actually READ the files (via their own file_read tool) and
reason about the contents. Results are synthesized into a summary.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.swell_analyze")

MAX_WORKERS = int(os.environ.get("TSUNAMI_MAX_WORKERS", "16"))


class SwellAnalyze(BaseTool):
    """Read many files in parallel via eddy workers and extract patterns."""

    name = "swell_analyze"
    description = (
        "Analyze ALL files in a directory using parallel eddy workers. "
        "Each eddy reads its assigned file(s) and answers the question. "
        "Results are synthesized. Use for analyzing 20+ files."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory containing files to analyze"},
                "question": {"type": "string", "description": "What to extract from each file"},
                "pattern": {"type": "string", "description": "Glob pattern for files", "default": "*.md"},
                "output_path": {"type": "string", "description": "Where to save results", "default": ""},
            },
            "required": ["directory", "question"],
        }

    async def execute(self, directory: str = "", question: str = "",
                      pattern: str = "*.md", output_path: str = "", **kwargs) -> ToolResult:
        if not directory or not question:
            return ToolResult("directory and question required", is_error=True)

        # Resolve directory
        root = Path(directory).expanduser().resolve()
        if not root.exists():
            stripped = directory.lstrip("/")
            root = Path(self.config.workspace_dir).parent / stripped
        if not root.exists():
            root = Path(self.config.workspace_dir).parent / directory.replace("/workspace/", "workspace/")
        if not root.exists():
            return ToolResult(f"Directory not found: {directory}", is_error=True)

        files = sorted(root.glob(pattern))
        if not files:
            return ToolResult(f"No {pattern} files in {directory}", is_error=True)

        log.info(f"Swell analyzing {len(files)} files with up to {MAX_WORKERS} eddies")

        from ..eddy import run_swarm, format_swarm_results

        # Build a task per file (or batch files for fewer workers)
        if len(files) <= MAX_WORKERS:
            # One file per eddy
            tasks = [
                f"Read the file '{f}' and answer: {question}. Be concise — one paragraph max."
                for f in files
            ]
        else:
            # Batch files across workers
            batch_size = (len(files) + MAX_WORKERS - 1) // MAX_WORKERS
            tasks = []
            for i in range(0, len(files), batch_size):
                batch = files[i:i + batch_size]
                file_list = ", ".join(str(f) for f in batch)
                tasks.append(
                    f"Read these files and answer '{question}' for each: {file_list}. "
                    f"One sentence per file."
                )

        workdir = str(root)
        results = await run_swarm(
            tasks=tasks,
            workdir=workdir,
            max_concurrent=min(MAX_WORKERS, len(tasks)),
        )

        # Save results to disk
        if not output_path:
            output_path = str(root / "_swarm_results.txt")
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            for r in results:
                status = "OK" if r.success else "FAIL"
                f.write(f"[{status}] {r.task[:80]}...\n{r.output}\n\n")

        # Build summary
        succeeded = sum(1 for r in results if r.success)
        total_tools = sum(r.tool_calls for r in results)

        summary = f"Analyzed {len(files)} files via {len(tasks)} eddies ({succeeded} succeeded, {total_tools} tool calls).\n"
        summary += f"Results saved to {output_path}\n\n"

        # Include top findings in context
        for r in results:
            if r.success and r.output:
                summary += f"• {r.output[:300]}\n"

        summary += "\nUse message_result to deliver these findings."
        return ToolResult(summary)
