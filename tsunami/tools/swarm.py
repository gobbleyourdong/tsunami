"""Auto-swarm — queen (27B) dispatches bees (2B workers) for parallel tasks.

The queen detects parallelizable work and spawns 2B workers.
Workers run in parallel via async, each with their own context.
Results merge back to the queen.

ENV: TSUNAMI_MAX_WORKERS (default 4)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.swarm")

MAX_WORKERS = int(os.environ.get("TSUNAMI_MAX_WORKERS", "4"))
BEE_ENDPOINT = os.environ.get("TSUNAMI_BEE_ENDPOINT", "http://localhost:8092")


class Swarm(BaseTool):
    """Dispatch parallel 2B workers for batch tasks. The queen sends bees."""

    name = "swarm"
    description = (
        f"Dispatch up to {MAX_WORKERS} parallel workers (2B model) for batch tasks. "
        "Give each worker a specific subtask string. Workers run simultaneously. "
        "Use for: reading many files, processing batches, parallel research. "
        "Returns all results when every worker finishes."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": f"List of subtask prompts (max {MAX_WORKERS}). Each runs on a 2B worker in parallel.",
                },
            },
            "required": ["tasks"],
        }

    async def execute(self, tasks: list = None, **kwargs) -> ToolResult:
        if not tasks:
            return ToolResult("tasks list required", is_error=True)

        tasks = tasks[:MAX_WORKERS]
        log.info(f"Swarming {len(tasks)} workers on {BEE_ENDPOINT}")

        async def run_bee(i: int, task: str) -> dict:
            """Run a single 2B worker."""
            try:
                import httpx
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(
                        f"{BEE_ENDPOINT}/v1/chat/completions",
                        json={
                            "model": "qwen",
                            "messages": [
                                {"role": "system", "content": "You are a focused worker. Complete the task concisely. Output only the result."},
                                {"role": "user", "content": task},
                            ],
                            "max_tokens": 2048,
                        },
                        headers={"Authorization": "Bearer not-needed"},
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        return {"worker": i, "status": "done", "result": content[:2000]}
                    else:
                        return {"worker": i, "status": "error", "result": f"HTTP {resp.status_code}"}
            except Exception as e:
                return {"worker": i, "status": "error", "result": str(e)[:200]}

        # Run all bees in parallel
        results = await asyncio.gather(*[run_bee(i, t) for i, t in enumerate(tasks)])

        # Format results
        lines = [f"Swarm complete: {len(results)} workers"]
        for r in results:
            status = "✓" if r["status"] == "done" else "✗"
            lines.append(f"\n[Worker {r['worker']}] {status}")
            lines.append(r["result"][:500])

        return ToolResult("\n".join(lines))
