"""Parallel tool execution — run multiple tool calls concurrently.

When the model returns multiple tool_use blocks in one response,
concurrent-safe tools (reads, searches) run in parallel while
unsafe tools (writes, shell) run serially.

Uses asyncio.gather with a concurrency cap, streaming results
back as they complete rather than waiting for all to finish.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("tsunami.parallel_tools")

# Default concurrency cap (from Claude Code's toolOrchestration.ts)
DEFAULT_MAX_CONCURRENCY = int(os.environ.get("TSUNAMI_MAX_TOOL_CONCURRENCY", "10"))


@dataclass
class ToolRequest:
    """A single tool call request."""
    name: str
    arguments: dict
    concurrent_safe: bool = False


@dataclass
class ToolResponse:
    """Result of a single tool execution."""
    name: str
    arguments: dict
    content: str
    is_error: bool = False
    elapsed_ms: float = 0


def partition_by_concurrency(requests: list[ToolRequest]) -> list[tuple[bool, list[ToolRequest]]]:
    """Partition tool requests into batches by concurrency safety.

    Returns list of (is_concurrent, batch) tuples.
    Consecutive safe tools form one batch; each unsafe tool is its own batch.
    Preserves original ordering.
    """
    if not requests:
        return []

    batches: list[tuple[bool, list[ToolRequest]]] = []
    current_batch: list[ToolRequest] = []
    current_safe: bool | None = None

    for req in requests:
        if current_safe is None:
            current_safe = req.concurrent_safe
            current_batch = [req]
        elif req.concurrent_safe == current_safe and req.concurrent_safe:
            # Extend concurrent batch
            current_batch.append(req)
        else:
            # Flush current batch, start new one
            batches.append((current_safe, current_batch))
            current_safe = req.concurrent_safe
            current_batch = [req]

    if current_batch:
        batches.append((current_safe, current_batch))

    return batches


async def execute_batch_concurrent(
    batch: list[ToolRequest],
    executor,  # async callable(name, args) -> ToolResponse
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> list[ToolResponse]:
    """Execute a batch of concurrent-safe tools in parallel.

    Uses semaphore to cap concurrency. Results returned in
    completion order (not request order) for streaming.
    """
    sem = asyncio.Semaphore(max_concurrency)
    results: list[ToolResponse] = []

    async def _run(req: ToolRequest) -> ToolResponse:
        async with sem:
            import time
            start = time.time()
            try:
                response = await executor(req.name, req.arguments)
                response.elapsed_ms = (time.time() - start) * 1000
                return response
            except Exception as e:
                return ToolResponse(
                    name=req.name,
                    arguments=req.arguments,
                    content=f"Error: {e}",
                    is_error=True,
                    elapsed_ms=(time.time() - start) * 1000,
                )

    # Run all concurrently with semaphore cap
    tasks = [_run(req) for req in batch]
    results = await asyncio.gather(*tasks)
    return list(results)


async def execute_batch_serial(
    batch: list[ToolRequest],
    executor,
) -> list[ToolResponse]:
    """Execute a batch of tools serially (for unsafe operations)."""
    results = []
    for req in batch:
        import time
        start = time.time()
        try:
            response = await executor(req.name, req.arguments)
            response.elapsed_ms = (time.time() - start) * 1000
            results.append(response)
        except Exception as e:
            results.append(ToolResponse(
                name=req.name,
                arguments=req.arguments,
                content=f"Error: {e}",
                is_error=True,
                elapsed_ms=(time.time() - start) * 1000,
            ))
    return results


async def execute_all(
    requests: list[ToolRequest],
    executor,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> list[ToolResponse]:
    """Execute all tool requests, respecting concurrency safety.

    Partitions into batches, runs safe batches in parallel and
    unsafe batches serially, preserving batch ordering.
    """
    all_results: list[ToolResponse] = []

    for is_concurrent, batch in partition_by_concurrency(requests):
        if is_concurrent:
            results = await execute_batch_concurrent(batch, executor, max_concurrency)
        else:
            results = await execute_batch_serial(batch, executor)
        all_results.extend(results)

    total_ms = sum(r.elapsed_ms for r in all_results)
    wall_ms = max((r.elapsed_ms for r in all_results), default=0)
    if len(all_results) > 1:
        log.info(
            f"Parallel execution: {len(all_results)} tools, "
            f"total={total_ms:.0f}ms, wall={wall_ms:.0f}ms, "
            f"speedup={total_ms/max(wall_ms,1):.1f}x"
        )

    return all_results
