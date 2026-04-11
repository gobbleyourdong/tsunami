#!/usr/bin/env python3
"""Integration eval — runs REAL agent builds, not fake tool results.

Unlike eval_toolcall.py (format test with fake responses), this runs
the actual Tsunami agent loop against a real model server, real file
system, real npm builds. Measures what actually matters:

  1. Does it scaffold?
  2. Does it write code?
  3. Does it compile?
  4. Does it deliver?
  5. How many iterations?
  6. What went wrong if it failed?

Usage:
  python training/eval_integration.py --endpoint http://localhost:8095
  python training/eval_integration.py --endpoint http://localhost:8095 --filter easy
  python training/eval_integration.py --endpoint http://localhost:8095 --timeout 120
"""

import argparse
import asyncio
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_integration")

EVAL_PROMPTS = [
    # Easy — single component, should complete in <10 iters
    {"id": "IE01", "level": "easy", "prompt": "Build a counter app with plus and minus buttons"},
    {"id": "IE02", "level": "easy", "prompt": "Build a digital clock"},
    {"id": "IE03", "level": "easy", "prompt": "Build a color picker"},

    # Medium — multiple components, state management
    {"id": "IM01", "level": "medium", "prompt": "Build a todo app with add, delete, and mark complete"},
    {"id": "IM02", "level": "medium", "prompt": "Build a pomodoro timer with start, pause, reset"},
    {"id": "IM03", "level": "medium", "prompt": "Build a quiz app with 5 questions and a score"},

    # Hard — multi-file, complex logic
    {"id": "IH01", "level": "hard", "prompt": "Build a kanban board with 3 columns and draggable cards"},
    {"id": "IH02", "level": "hard", "prompt": "Build a markdown editor with live preview"},
    {"id": "IH03", "level": "hard", "prompt": "Build an expense tracker with categories and a chart"},
]


@dataclass
class IntegrationResult:
    prompt_id: str
    level: str
    prompt: str
    # Core outcomes
    scaffolded: bool = False
    files_written: int = 0
    compiled: bool = False
    delivered: bool = False
    iterations: int = 0
    wall_clock_s: float = 0
    tool_sequence: list = field(default_factory=list)
    tool_args: list = field(default_factory=list)  # (tool_name, args_dict) per call
    tool_results: list = field(default_factory=list)  # (tool_name, result_text) per call
    errors: list = field(default_factory=list)
    failure_mode: str = ""
    # Agentic diagnostics
    diagnostics: dict = field(default_factory=dict)


async def run_agent_build(endpoint: str, prompt: str, timeout: int = 180,
                          workspace: str = "/tmp/tsunami_eval") -> IntegrationResult:
    """Run a real Tsunami agent build and capture everything."""
    result = IntegrationResult(prompt_id="", level="", prompt=prompt)

    # Clean workspace (ignore errors from node_modules permission issues)
    ws = Path(workspace)
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()

    try:
        # Import and configure Tsunami
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from tsunami.config import TsunamiConfig
        from tsunami.agent import Agent

        config = TsunamiConfig(
            model_backend="api",
            model_name="eval",
            model_endpoint=endpoint,
            eddy_endpoint=endpoint,
            workspace_dir=str(ws),
            max_iterations=60,
            temperature=0.1,
        )

        agent = Agent(config)

        # Monkey-patch to capture tool calls, args, and results
        original_step = agent._step
        tool_log = []
        tool_args_log = []
        tool_results_log = []

        # Wrap tool execution to capture args + results
        original_registry_get = agent.registry.get
        def tracking_get(name):
            tool = original_registry_get(name)
            if tool is None:
                return None
            original_execute = tool.execute
            async def tracked_execute(**kwargs):
                tool_args_log.append((name, dict(kwargs)))
                r = await original_execute(**kwargs)
                tool_results_log.append((name, str(r.content)[:500] if r else ""))
                return r
            tool.execute = tracked_execute
            return tool
        agent.registry.get = tracking_get

        async def tracking_step():
            r = await original_step()
            if agent._tool_history:
                last = agent._tool_history[-1]
                tool_log.append(last)
            return r

        agent._step = tracking_step

        # Run with timeout
        try:
            output = await asyncio.wait_for(
                agent.run(prompt),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            output = "TIMEOUT"
            result.failure_mode = f"Timed out after {timeout}s"

        result.wall_clock_s = time.monotonic() - t0
        result.iterations = agent.state.iteration
        result.tool_sequence = tool_log
        result.tool_args = tool_args_log
        result.tool_results = tool_results_log
        result.delivered = agent.state.task_complete

        # Check what happened
        deliverables = ws / "deliverables"
        if deliverables.exists():
            projects = sorted(
                [d for d in deliverables.iterdir() if d.is_dir() and (d / "package.json").exists()],
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if projects:
                result.scaffolded = True
                project = projects[0]

                # Count files written
                src = project / "src"
                if src.exists():
                    result.files_written = sum(1 for f in src.rglob("*.tsx") if f.is_file())
                    result.files_written += sum(1 for f in src.rglob("*.ts") if f.is_file())

                # Check if it compiled
                dist = project / "dist"
                if dist.exists() and (dist / "index.html").exists():
                    result.compiled = True

                # Check for build errors in the tool sequence
                # (would need to capture tool results too — simplified here)

        # === AGENTIC DIAGNOSTICS ===
        diag = {}

        # 1. PATH PROBLEMS — wrong cd paths in shell_exec
        path_errors = 0
        bad_paths = []
        for name, args in result.tool_args:
            if name == "shell_exec":
                cmd = args.get("command", "") if isinstance(args, dict) else str(args)
                # Catch: cd workspace/deliverables (should be cd deliverables/)
                if "cd workspace/deliverables" in cmd and "cd ./workspace" not in cmd:
                    path_errors += 1
                    bad_paths.append(cmd[:80])
                # Catch: cd /home/.../workspace (absolute path to workspace)
                if "/workspace/deliverables" in cmd and cmd.startswith("cd /"):
                    path_errors += 1
                    bad_paths.append(cmd[:80])
        diag["path_errors"] = path_errors
        if bad_paths:
            diag["bad_paths"] = bad_paths

        # 2. SYNTAX ERRORS — vite build failures from tool results
        build_attempts = 0
        build_failures = 0
        vite_errors = []
        for name, res_text in result.tool_results:
            if name == "shell_exec" and ("vite build" in str(res_text) or "npx vite" in str(res_text)):
                build_attempts += 1
                if "Error" in str(res_text) or "error" in str(res_text):
                    build_failures += 1
                    # Extract the error
                    err = str(res_text)[:200]
                    vite_errors.append(err)
        diag["build_attempts"] = build_attempts
        diag["build_failures"] = build_failures
        diag["build_success_rate"] = f"{(build_attempts-build_failures)/max(build_attempts,1)*100:.0f}%"
        if vite_errors:
            diag["vite_errors"] = vite_errors

        # 3. ERROR RECOVERY — did the model fix errors or just retry?
        shell_loop = 0
        prev_was_shell = False
        for name in result.tool_sequence:
            if name == "shell_exec":
                if prev_was_shell:
                    shell_loop += 1
                prev_was_shell = True
            else:
                prev_was_shell = False
        diag["shell_exec_loops"] = shell_loop  # consecutive shell_exec without file_edit between

        # Check if file_edit follows build failure (good recovery)
        recovery_attempts = 0
        for j in range(len(result.tool_results) - 1):
            name, res = result.tool_results[j]
            if name == "shell_exec" and "Error" in str(res):
                # What's the next tool?
                if j + 1 < len(result.tool_sequence):
                    next_tool = result.tool_sequence[j + 1] if j + 1 < len(result.tool_sequence) else ""
                    if next_tool in ("file_edit", "file_write", "file_read"):
                        recovery_attempts += 1
        diag["error_recovery_attempts"] = recovery_attempts

        # 4. MISSING QA — delivered without undertow
        used_undertow = "undertow" in result.tool_sequence
        diag["used_undertow"] = used_undertow
        if result.delivered and not used_undertow:
            diag["missing_qa"] = True

        # 5. MISSING PARAMS — file_write without path or content
        missing_params = 0
        for name, args in result.tool_args:
            if isinstance(args, dict):
                if name == "file_write" and ("path" not in args or "content" not in args):
                    missing_params += 1
                if name == "file_edit" and ("path" not in args or "old_text" not in args):
                    missing_params += 1
        diag["missing_params"] = missing_params

        # 6. TOOL DIVERSITY — how many unique tools used
        unique_tools = len(set(result.tool_sequence))
        diag["unique_tools"] = unique_tools
        diag["used_plan"] = "plan_update" in result.tool_sequence
        diag["used_swell"] = "swell" in result.tool_sequence
        diag["used_search"] = "search_web" in result.tool_sequence
        diag["used_message_chat"] = "message_chat" in result.tool_sequence

        # 7. STALL DETECTION — same tool called 3+ times consecutively
        stalls = []
        if len(result.tool_sequence) >= 3:
            for j in range(2, len(result.tool_sequence)):
                if (result.tool_sequence[j] == result.tool_sequence[j-1] == result.tool_sequence[j-2]):
                    stalls.append(f"{result.tool_sequence[j]} x3 at iter {j}")
        diag["stalls"] = stalls

        # 8. file_edit HALLUCINATION — edit failures
        edit_failures = 0
        for name, res in result.tool_results:
            if name == "file_edit" and ("not found" in str(res).lower() or "0 matches" in str(res).lower()):
                edit_failures += 1
        diag["edit_failures"] = edit_failures

        # 9. LINTING — did model react to vite error feedback?
        lint_reacted = 0
        for j in range(len(result.tool_results)):
            name, res = result.tool_results[j]
            if name == "shell_exec" and "Error" in str(res) and j + 1 < len(result.tool_sequence):
                next_tool = result.tool_sequence[j + 1]
                if next_tool in ("file_edit", "file_write", "file_read", "message_chat"):
                    lint_reacted += 1
        diag["lint_reactions"] = lint_reacted

        result.diagnostics = diag

        # Classify failure mode with richer diagnostics
        if not result.delivered:
            if not result.scaffolded:
                result.failure_mode = result.failure_mode or "Never scaffolded"
            elif result.files_written == 0:
                result.failure_mode = result.failure_mode or "Scaffolded but never wrote code"
            elif path_errors > 0:
                result.failure_mode = result.failure_mode or f"Path errors ({path_errors}): {bad_paths[0]}"
            elif build_failures > 0 and shell_loop >= 2:
                result.failure_mode = result.failure_mode or f"Shell loop ({shell_loop}x): retried build without fixing code"
            elif build_failures > 0 and recovery_attempts == 0:
                result.failure_mode = result.failure_mode or "Build failed, no error recovery attempted"
            elif not result.compiled:
                result.failure_mode = result.failure_mode or f"Build failed ({build_failures}/{build_attempts}): {vite_errors[0][:100] if vite_errors else 'unknown'}"
            else:
                result.failure_mode = result.failure_mode or "Compiled but didn't deliver"

    except Exception as e:
        result.wall_clock_s = time.monotonic() - t0
        result.failure_mode = f"Exception: {str(e)[:200]}"
        result.errors.append(str(e))

    return result


async def main():
    parser = argparse.ArgumentParser(description="Integration eval — real agent builds")
    parser.add_argument("--endpoint", default="http://localhost:8095")
    parser.add_argument("--filter", default=None, choices=["easy", "medium", "hard"])
    parser.add_argument("--timeout", type=int, default=180, help="Per-build timeout in seconds")
    parser.add_argument("--output", default="workspace/training_data/eval_integration_results.json")
    args = parser.parse_args()

    prompts = EVAL_PROMPTS
    if args.filter:
        prompts = [p for p in prompts if p["level"] == args.filter]

    log.info(f"Running {len(prompts)} integration builds against {args.endpoint}")

    results = []
    for p in prompts:
        log.info(f"\n{'='*50}")
        log.info(f"  {p['id']} [{p['level']}] {p['prompt'][:60]}")
        log.info(f"{'='*50}")

        r = await run_agent_build(
            args.endpoint, p["prompt"], timeout=args.timeout,
        )
        r.prompt_id = p["id"]
        r.level = p["level"]

        status = "PASS" if r.delivered and r.compiled else "FAIL"
        log.info(
            f"  {status} | iters={r.iterations} files={r.files_written} "
            f"compiled={r.compiled} delivered={r.delivered} "
            f"time={r.wall_clock_s:.1f}s"
        )
        if r.failure_mode:
            log.info(f"  FAILURE: {r.failure_mode}")
        if r.tool_sequence:
            seq = " → ".join(r.tool_sequence[:15])
            if len(r.tool_sequence) > 15:
                seq += f" ... ({len(r.tool_sequence)} total)"
            log.info(f"  TOOLS: {seq}")

        results.append(r)

    # Report
    print(f"\n{'='*60}")
    print(f"  INTEGRATION EVAL RESULTS")
    print(f"{'='*60}\n")

    total = len(results)
    delivered = sum(1 for r in results if r.delivered)
    compiled = sum(1 for r in results if r.compiled)
    scaffolded = sum(1 for r in results if r.scaffolded)

    print(f"  Scaffolded: {scaffolded}/{total}")
    print(f"  Compiled:   {compiled}/{total}")
    print(f"  Delivered:  {delivered}/{total}")
    print(f"  Success:    {sum(1 for r in results if r.delivered and r.compiled)}/{total}")
    print(f"  Avg iters:  {sum(r.iterations for r in results)/total:.1f}")
    print(f"  Avg time:   {sum(r.wall_clock_s for r in results)/total:.1f}s")

    # Failure taxonomy
    failures = [r for r in results if not (r.delivered and r.compiled)]
    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for r in failures:
            print(f"    {r.prompt_id}: {r.failure_mode}")
            if r.tool_sequence:
                print(f"      Tools: {' → '.join(r.tool_sequence[:10])}")

    # Agentic diagnostics summary
    all_diags = [r.diagnostics for r in results if r.diagnostics]
    if all_diags:
        print(f"\n  AGENTIC DIAGNOSTICS:")
        total_path = sum(d.get("path_errors", 0) for d in all_diags)
        total_shell_loop = sum(d.get("shell_exec_loops", 0) for d in all_diags)
        total_edit_fail = sum(d.get("edit_failures", 0) for d in all_diags)
        total_missing_params = sum(d.get("missing_params", 0) for d in all_diags)
        total_missing_qa = sum(1 for d in all_diags if d.get("missing_qa"))
        total_build_fail = sum(d.get("build_failures", 0) for d in all_diags)
        total_build_attempt = sum(d.get("build_attempts", 0) for d in all_diags)
        total_recovery = sum(d.get("error_recovery_attempts", 0) for d in all_diags)
        total_lint = sum(d.get("lint_reactions", 0) for d in all_diags)
        total_stalls = sum(len(d.get("stalls", [])) for d in all_diags)
        used_plan = sum(1 for d in all_diags if d.get("used_plan"))
        used_swell = sum(1 for d in all_diags if d.get("used_swell"))
        used_undertow_count = sum(1 for d in all_diags if d.get("used_undertow"))
        used_search = sum(1 for d in all_diags if d.get("used_search"))
        used_chat = sum(1 for d in all_diags if d.get("used_message_chat"))

        n = len(all_diags)
        print(f"    Path errors:        {total_path:>4}  {'BAD' if total_path > 0 else 'OK'}")
        print(f"    Shell loops:        {total_shell_loop:>4}  {'BAD' if total_shell_loop > 2 else 'OK'}")
        print(f"    Edit hallucinations:{total_edit_fail:>4}  {'BAD' if total_edit_fail > 0 else 'OK'}")
        print(f"    Missing params:     {total_missing_params:>4}  {'BAD' if total_missing_params > 0 else 'OK'}")
        print(f"    Missing QA:         {total_missing_qa:>4}/{n}  {'BAD' if total_missing_qa > n//2 else 'OK'}")
        print(f"    Build attempts:     {total_build_attempt:>4}")
        print(f"    Build failures:     {total_build_fail:>4}  ({100*total_build_fail/max(total_build_attempt,1):.0f}%)")
        print(f"    Error recovery:     {total_recovery:>4}  (fix attempts after build fail)")
        print(f"    Lint reactions:     {total_lint:>4}  (read/edit/fix after vite error)")
        print(f"    Stalls (3x repeat): {total_stalls:>4}  {'BAD' if total_stalls > 0 else 'OK'}")
        print(f"    Used plan_update:   {used_plan:>4}/{n}")
        print(f"    Used swell:         {used_swell:>4}/{n}")
        print(f"    Used undertow:      {used_undertow_count:>4}/{n}")
        print(f"    Used search_web:    {used_search:>4}/{n}")
        print(f"    Used message_chat:  {used_chat:>4}/{n}")

        # Collect all unique vite errors
        all_vite = []
        for d in all_diags:
            all_vite.extend(d.get("vite_errors", []))
        if all_vite:
            print(f"\n  VITE ERROR PATTERNS:")
            from collections import Counter
            # Simplify errors to patterns
            patterns = Counter()
            for err in all_vite:
                if "Cannot find module" in err:
                    patterns["Missing module/import"] += 1
                elif "is not assignable" in err:
                    patterns["Type error"] += 1
                elif "Unexpected token" in err or "Expected" in err:
                    patterns["Syntax error"] += 1
                elif "No such file" in err:
                    patterns["File not found"] += 1
                else:
                    patterns[err[:60]] += 1
            for pattern, count in patterns.most_common(10):
                print(f"      [{count}x] {pattern}")

    # Per-level
    for level in ["easy", "medium", "hard"]:
        level_results = [r for r in results if r.level == level]
        if level_results:
            n = len(level_results)
            ok = sum(1 for r in level_results if r.delivered and r.compiled)
            avg_iter = sum(r.iterations for r in level_results) / n
            print(f"\n  {level.upper()}: {ok}/{n} ({100*ok/n:.0f}%) avg {avg_iter:.0f} iters")

    # Save results
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "endpoint": args.endpoint,
            "results": [
                {
                    "id": r.prompt_id, "level": r.level, "prompt": r.prompt,
                    "scaffolded": r.scaffolded, "files_written": r.files_written,
                    "compiled": r.compiled, "delivered": r.delivered,
                    "iterations": r.iterations, "wall_clock_s": r.wall_clock_s,
                    "tool_sequence": r.tool_sequence, "failure_mode": r.failure_mode,
                }
                for r in results
            ],
        }, f, indent=2)
    log.info(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
