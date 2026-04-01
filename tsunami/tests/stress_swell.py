#!/usr/bin/env python3
"""Stress test the eddy swell — hammer the 2B until it breaks.

Runs against live 2B server on :8092. Tests:
1. Single eddy with tool use
2. 4 parallel eddies (fills all slots)
3. 8 parallel eddies (oversubscribed — tests queuing)
4. 16 parallel eddies (extreme — should degrade gracefully)
5. Eddy with bad task (error handling)
6. Eddy with huge output (context pressure)
7. Rapid fire — 20 quick tasks back-to-back
8. Mixed workloads — reads + shell + grep simultaneously

Usage: python3 -m tsunami.tests.stress_swell
"""

import asyncio
import os
import sys
import tempfile
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tsunami.eddy import run_bee, run_swarm, format_swarm_results, BeeResult

EDDY_ENDPOINT = "http://localhost:8092"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def header(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def result_line(name, result, elapsed=None):
    status = "PASS" if result.success else "FAIL"
    t = f" ({elapsed:.1f}s)" if elapsed else f" ({result.elapsed_ms:.0f}ms)"
    tools = f" [{result.tool_calls} tools, {result.turns} turns]" if result.tool_calls else ""
    print(f"  {status} {name}{t}{tools}")
    if result.error:
        print(f"       error: {result.error}")
    if result.output:
        print(f"       output: {result.output[:100]}")


async def test_single_bee():
    """Single eddy with tool use — baseline."""
    header("TEST 1: Single eddy with tool use")
    start = time.time()
    r = await run_bee(
        "Read the file tsunami/config.py and tell me how many dataclass fields it has.",
        workdir=PROJECT_ROOT,
        endpoint=EDDY_ENDPOINT,
    )
    result_line("single eddy + file_read", r, time.time() - start)
    return r.success


async def test_4_parallel():
    """4 eddies = exact slot count."""
    header("TEST 2: 4 parallel eddies (filling all slots)")
    tasks = [
        "Run 'ls tsunami/*.py | wc -l' and tell me the count.",
        "Read tsunami/__init__.py and tell me what it says.",
        "Run 'python3 --version' and report the version.",
        "Search for 'class.*BaseTool' in tsunami/tools/ and tell me how many matches.",
    ]
    start = time.time()
    results = await run_swarm(tasks, workdir=PROJECT_ROOT, max_concurrent=4, endpoint=EDDY_ENDPOINT)
    elapsed = time.time() - start
    for i, r in enumerate(results):
        result_line(f"eddy {i}", r)
    succeeded = sum(1 for r in results if r.success)
    print(f"\n  {succeeded}/{len(results)} succeeded in {elapsed:.1f}s")
    return succeeded == len(results)


async def test_8_oversubscribed():
    """8 eddies on 4 slots — tests queuing."""
    header("TEST 3: 8 parallel eddies (oversubscribed)")
    tasks = [f"What is {i} * {i+3}? Just the number." for i in range(8)]
    start = time.time()
    results = await run_swarm(tasks, workdir=PROJECT_ROOT, max_concurrent=8, endpoint=EDDY_ENDPOINT)
    elapsed = time.time() - start
    succeeded = sum(1 for r in results if r.success)
    errors = [r for r in results if not r.success]
    print(f"  {succeeded}/{len(results)} succeeded in {elapsed:.1f}s")
    for e in errors:
        print(f"  FAIL: {e.error}")
    return succeeded >= 6  # allow some failures under pressure


async def test_16_extreme():
    """16 eddies — extreme oversubscription."""
    header("TEST 4: 16 parallel eddies (extreme)")
    tasks = [f"Say the word 'eddy{i}' and nothing else." for i in range(16)]
    start = time.time()
    results = await run_swarm(tasks, workdir=PROJECT_ROOT, max_concurrent=16, endpoint=EDDY_ENDPOINT)
    elapsed = time.time() - start
    succeeded = sum(1 for r in results if r.success)
    print(f"  {succeeded}/{len(results)} succeeded in {elapsed:.1f}s")
    return succeeded >= 8  # expect degradation, but should mostly work


async def test_error_handling():
    """Eddy with impossible task — should fail gracefully."""
    header("TEST 5: Error handling")
    r = await run_bee(
        "Read the file /nonexistent/impossible/path.txt and summarize it.",
        workdir=PROJECT_ROOT,
        endpoint=EDDY_ENDPOINT,
    )
    result_line("impossible task", r)
    # Should complete (success or failure) without crashing
    return True  # pass as long as it didn't throw


async def test_context_pressure():
    """Eddy reading a large file — context pressure."""
    header("TEST 6: Context pressure (large file)")
    r = await run_bee(
        "Read tsunami/prompt.py and count how many times the word 'tool' appears.",
        workdir=PROJECT_ROOT,
        endpoint=EDDY_ENDPOINT,
        max_turns=5,
    )
    result_line("large file read", r)
    return r.success or r.turns > 0  # at least it tried


async def test_rapid_fire():
    """20 quick tasks back-to-back — throughput test."""
    header("TEST 7: Rapid fire (20 tasks)")
    tasks = [f"What is {i} + {i}? Just the number." for i in range(20)]
    start = time.time()
    results = await run_swarm(tasks, workdir=PROJECT_ROOT, max_concurrent=4, endpoint=EDDY_ENDPOINT)
    elapsed = time.time() - start
    succeeded = sum(1 for r in results if r.success)
    total_tools = sum(r.tool_calls for r in results)
    print(f"  {succeeded}/{len(results)} succeeded in {elapsed:.1f}s")
    print(f"  throughput: {len(results)/elapsed:.1f} tasks/s")
    print(f"  total tool calls: {total_tools}")
    return succeeded >= 15


async def test_mixed_workload():
    """Different tool types simultaneously."""
    header("TEST 8: Mixed workload")
    tasks = [
        "Read tsunami/eddy.py and count the number of functions defined (def keyword).",
        "Run 'find tsunami/ -name \"*.py\" | wc -l' and report the count.",
        "Search for 'async def' in tsunami/ and count matches.",
        "Read tsunami/config.py and list all the field names.",
    ]
    start = time.time()
    results = await run_swarm(tasks, workdir=PROJECT_ROOT, max_concurrent=4, endpoint=EDDY_ENDPOINT)
    elapsed = time.time() - start
    for i, r in enumerate(results):
        result_line(f"mixed {i}", r)
    succeeded = sum(1 for r in results if r.success)
    print(f"\n  {succeeded}/{len(results)} succeeded in {elapsed:.1f}s")
    return succeeded >= 3


async def main():
    print("\n  TSUNAMI SWELL STRESS TEST")
    print(f"  Target: {EDDY_ENDPOINT} (2B, 4 slots)")
    print(f"  Workdir: {PROJECT_ROOT}")

    tests = [
        ("single_bee", test_single_bee),
        ("4_parallel", test_4_parallel),
        ("8_oversubscribed", test_8_oversubscribed),
        ("16_extreme", test_16_extreme),
        ("error_handling", test_error_handling),
        ("context_pressure", test_context_pressure),
        ("rapid_fire", test_rapid_fire),
        ("mixed_workload", test_mixed_workload),
    ]

    results = {}
    total_start = time.time()

    for name, test_fn in tests:
        try:
            passed = await test_fn()
            results[name] = "PASS" if passed else "FAIL"
        except Exception as e:
            print(f"  CRASH: {e}")
            results[name] = "CRASH"

    total_elapsed = time.time() - total_start

    header("RESULTS")
    for name, status in results.items():
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {name}: {status}")

    passed = sum(1 for s in results.values() if s == "PASS")
    print(f"\n  {passed}/{len(results)} passed in {total_elapsed:.1f}s")

    return all(s == "PASS" for s in results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
