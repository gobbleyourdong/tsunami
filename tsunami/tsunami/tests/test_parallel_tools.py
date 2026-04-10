"""Tests for parallel tool execution."""

import asyncio
import pytest

from tsunami.parallel_tools import (
    ToolRequest,
    ToolResponse,
    partition_by_concurrency,
    execute_batch_concurrent,
    execute_batch_serial,
    execute_all,
    DEFAULT_MAX_CONCURRENCY,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestPartitionByConcurrency:
    """Partition tool calls into safe/unsafe batches."""

    def test_all_safe(self):
        reqs = [
            ToolRequest(name="file_read", arguments={}, concurrent_safe=True),
            ToolRequest(name="match_grep", arguments={}, concurrent_safe=True),
            ToolRequest(name="match_glob", arguments={}, concurrent_safe=True),
        ]
        batches = partition_by_concurrency(reqs)
        assert len(batches) == 1
        assert batches[0][0] is True  # concurrent
        assert len(batches[0][1]) == 3

    def test_all_unsafe(self):
        reqs = [
            ToolRequest(name="file_write", arguments={}, concurrent_safe=False),
            ToolRequest(name="shell_exec", arguments={}, concurrent_safe=False),
        ]
        batches = partition_by_concurrency(reqs)
        # Each unsafe tool is its own batch (since they can't be grouped)
        assert len(batches) == 2

    def test_mixed(self):
        reqs = [
            ToolRequest(name="file_read", arguments={}, concurrent_safe=True),
            ToolRequest(name="match_grep", arguments={}, concurrent_safe=True),
            ToolRequest(name="file_write", arguments={}, concurrent_safe=False),
            ToolRequest(name="file_read", arguments={}, concurrent_safe=True),
        ]
        batches = partition_by_concurrency(reqs)
        assert len(batches) == 3
        assert batches[0][0] is True   # safe batch
        assert batches[1][0] is False  # unsafe
        assert batches[2][0] is True   # safe batch

    def test_empty(self):
        assert partition_by_concurrency([]) == []

    def test_single(self):
        reqs = [ToolRequest(name="file_read", arguments={}, concurrent_safe=True)]
        batches = partition_by_concurrency(reqs)
        assert len(batches) == 1


class TestExecuteBatchConcurrent:
    """Parallel execution with semaphore."""

    def test_runs_all(self):
        async def executor(name, args):
            return ToolResponse(name=name, arguments=args, content=f"{name} done")

        reqs = [
            ToolRequest(name=f"tool_{i}", arguments={}, concurrent_safe=True)
            for i in range(5)
        ]
        results = run(execute_batch_concurrent(reqs, executor))
        assert len(results) == 5
        assert all(r.content.endswith("done") for r in results)

    def test_handles_errors(self):
        async def executor(name, args):
            if name == "bad":
                raise ValueError("boom")
            return ToolResponse(name=name, arguments=args, content="ok")

        reqs = [
            ToolRequest(name="good", arguments={}, concurrent_safe=True),
            ToolRequest(name="bad", arguments={}, concurrent_safe=True),
        ]
        results = run(execute_batch_concurrent(reqs, executor))
        assert len(results) == 2
        errors = [r for r in results if r.is_error]
        assert len(errors) == 1
        assert "boom" in errors[0].content

    def test_respects_concurrency_cap(self):
        running = 0
        max_running = 0

        async def executor(name, args):
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.01)
            running -= 1
            return ToolResponse(name=name, arguments=args, content="ok")

        reqs = [
            ToolRequest(name=f"t{i}", arguments={}, concurrent_safe=True)
            for i in range(20)
        ]
        run(execute_batch_concurrent(reqs, executor, max_concurrency=3))
        assert max_running <= 3

    def test_tracks_elapsed(self):
        async def executor(name, args):
            await asyncio.sleep(0.01)
            return ToolResponse(name=name, arguments=args, content="ok")

        reqs = [ToolRequest(name="t", arguments={}, concurrent_safe=True)]
        results = run(execute_batch_concurrent(reqs, executor))
        assert results[0].elapsed_ms > 0


class TestExecuteBatchSerial:
    """Serial execution for unsafe tools."""

    def test_runs_in_order(self):
        order = []

        async def executor(name, args):
            order.append(name)
            return ToolResponse(name=name, arguments=args, content="ok")

        reqs = [
            ToolRequest(name="first", arguments={}, concurrent_safe=False),
            ToolRequest(name="second", arguments={}, concurrent_safe=False),
            ToolRequest(name="third", arguments={}, concurrent_safe=False),
        ]
        run(execute_batch_serial(reqs, executor))
        assert order == ["first", "second", "third"]


class TestExecuteAll:
    """Full execution with partitioning."""

    def test_mixed_execution(self):
        call_order = []

        async def executor(name, args):
            call_order.append(name)
            return ToolResponse(name=name, arguments=args, content=f"{name} done")

        reqs = [
            ToolRequest(name="read_1", arguments={}, concurrent_safe=True),
            ToolRequest(name="read_2", arguments={}, concurrent_safe=True),
            ToolRequest(name="write_1", arguments={}, concurrent_safe=False),
            ToolRequest(name="read_3", arguments={}, concurrent_safe=True),
        ]
        results = run(execute_all(reqs, executor))
        assert len(results) == 4
        # write_1 should come after both reads complete
        write_idx = call_order.index("write_1")
        assert "read_1" in call_order[:write_idx] or "read_2" in call_order[:write_idx]

    def test_empty(self):
        async def executor(name, args):
            return ToolResponse(name=name, arguments=args, content="ok")
        results = run(execute_all([], executor))
        assert results == []
