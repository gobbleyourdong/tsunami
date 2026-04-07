#!/usr/bin/env python3
"""Run the full eval pyramid and produce a single report.

  Layer 1: Format (40 prompts, fake results, ~2 min)
  Layer 2: Scaffold Selection (12 prompts, single turn, ~1 min)
  Layer 3: Error Recovery (6 scenarios, single turn, ~1 min)
  Layer 4: Hack-Free (10 scenarios, single turn, ~1 min)
  Layer 5: Integration (9 prompts, full agent loop, ~30 min)

Usage:
  # Quick (layers 1-4, ~5 min)
  python training/eval_all.py --endpoint http://localhost:8095 --quick

  # Full (all 5 layers, ~35 min)
  python training/eval_all.py --endpoint http://localhost:8095

  # Compare to previous run
  python training/eval_all.py --endpoint http://localhost:8095 --quick --compare workspace/training_data/eval_previous.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix imports — add training/ to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_all")


def generate_markdown_report(report, prev, format_detail, scaffold_detail,
                             recovery_detail, hackfree_detail, int_detail):
    """Generate a full markdown eval report."""
    lines = []
    w = lines.append

    ts = report["timestamp"]
    elapsed = report.get("elapsed_s", 0)
    w(f"# Tsunami Eval Report")
    w(f"")
    w(f"**Date**: {ts}  ")
    w(f"**Endpoint**: {report.get('endpoint', 'unknown')}  ")
    w(f"**Elapsed**: {elapsed:.0f}s  ")
    w(f"**Layers**: {', '.join(report.get('layers_run', []))}")
    w(f"")

    # --- SCOREBOARD ---
    w(f"## Scoreboard")
    w(f"")
    w(f"| Layer | Score | Pct | Delta |")
    w(f"|-------|-------|-----|-------|")
    layer_order = ["format", "scaffold", "recovery", "hackfree", "integration"]
    for layer in layer_order:
        if layer not in report:
            continue
        d = report[layer]
        p, t = d["passed"], d["total"]
        delta = ""
        if prev and layer in prev:
            diff = p - prev[layer]["passed"]
            if diff > 0:
                delta = f"+{diff}"
            elif diff < 0:
                delta = str(diff)
            else:
                delta = "="
        w(f"| {layer} | {p}/{t} | {d['pct']} | {delta} |")
    w(f"")

    # --- LAYER 1: FORMAT ---
    if format_detail:
        w(f"## L1: Format")
        w(f"")
        d = report["format"]
        w(f"- **Tool call produced**: {d['passed']}/{d['total']}")
        w(f"- **Valid tool name**: {d['valid_name']}/{d['total']}")
        w(f"- **Correct first tool**: {d['correct_first']}/{d['total']}")
        w(f"")

        # Group by level
        by_level = {}
        for r in format_detail:
            by_level.setdefault(r["level"], []).append(r)

        for level in ["trivial", "easy", "medium", "hard", "extreme"]:
            group = by_level.get(level, [])
            if not group:
                continue
            n = len(group)
            ok = sum(1 for r in group if r["pass"])
            w(f"### {level.upper()} ({ok}/{n})")
            w(f"")
            w(f"| ID | Prompt | Pass | Got | Expected | ms |")
            w(f"|----|--------|------|-----|----------|----|")
            for r in group:
                status = "PASS" if r["pass"] else "FAIL"
                prompt = r["prompt"][:45]
                w(f"| {r['id']} | {prompt} | {status} | {r['tool']} | {r['expected']} | {r['latency_ms']} |")
            w(f"")

        # Failures summary
        fails = [r for r in format_detail if not r["pass"]]
        if fails:
            w(f"### Failures ({len(fails)})")
            w(f"")
            for r in fails:
                w(f"- **{r['id']}** `{r['prompt'][:50]}` — got `{r['tool']}`, expected `{r['expected']}`{' ERROR: ' + r['error'] if r['error'] else ''}")
            w(f"")

    # --- LAYER 2: SCAFFOLD ---
    if scaffold_detail:
        w(f"## L2: Scaffold Selection")
        w(f"")
        d = report["scaffold"]
        w(f"**Score**: {d['passed']}/{d['total']} ({d['pct']})")
        w(f"")
        w(f"| ID | Prompt | Pass | Expected | Got Name | Deps |")
        w(f"|----|--------|------|----------|----------|------|")
        for r in scaffold_detail:
            prompt = r.get("prompt", "")[:40]
            deps = ", ".join(r.get("dependencies", [])[:3])
            w(f"| {r['id']} | {prompt} | {r['status']} | {r['expected']} | {r.get('project_name', '')} | {deps} |")
        w(f"")

        fails = [r for r in scaffold_detail if r["status"] == "FAIL"]
        if fails:
            w(f"### Failures")
            w(f"")
            for r in fails:
                w(f"- **{r['id']}**: {r.get('reason', '')}")
            w(f"")

    # --- LAYER 3: ERROR RECOVERY ---
    if recovery_detail:
        w(f"## L3: Error Recovery")
        w(f"")
        d = report["recovery"]
        w(f"**Score**: {d['passed']}/{d['total']} ({d['pct']})")
        w(f"")
        w(f"| ID | Scenario | Pass | Expected | Got | Issue |")
        w(f"|----|----------|------|----------|-----|-------|")
        for r in recovery_detail:
            issue = r.get("reason", "")[:50]
            w(f"| {r['id']} | {r['name']} | {r['status']} | {r['expected_tool']} | {r.get('actual_tool', 'NONE')} | {issue} |")
        w(f"")

        fails = [r for r in recovery_detail if r["status"] == "FAIL"]
        if fails:
            w(f"### Failures")
            w(f"")
            for r in fails:
                bad = " (retried without fixing)" if r.get("bad_retry") else ""
                w(f"- **{r['id']} {r['name']}**: {r.get('reason', '')}{bad}")
            w(f"")

    # --- LAYER 4: HACK-FREE ---
    if hackfree_detail:
        w(f"## L4: Hack-Free Behavior")
        w(f"")
        d = report["hackfree"]
        w(f"**Score**: {d['passed']}/{d['total']} ({d['pct']})")
        w(f"")
        w(f"| ID | Hack | Pass | Expected | Got | Issue |")
        w(f"|----|------|------|----------|-----|-------|")
        for r in hackfree_detail:
            issue = r.get("reason", "")[:50]
            w(f"| {r['id']} | {r['hack']} | {r['status']} | {r['expected']} | {r.get('actual', 'NONE')} | {issue} |")
        w(f"")

        still = d.get("still_needs_hacks", [])
        if still:
            w(f"### Still Needs Hacks")
            w(f"")
            for hack in still:
                w(f"- {hack}")
            w(f"")

    # --- LAYER 5: INTEGRATION ---
    if int_detail:
        w(f"## L5: Integration")
        w(f"")
        d = report["integration"]
        w(f"**Score**: {d['passed']}/{d['total']} ({d['pct']})  ")
        w(f"**Avg iters**: {d['avg_iters']}  ")
        w(f"**Avg time**: {d['avg_time_s']}s")
        w(f"")

        w(f"### Per-Build Results")
        w(f"")
        w(f"| ID | Level | Prompt | Pass | Iters | Time | Files | Failure |")
        w(f"|----|-------|--------|------|-------|------|-------|---------|")
        for r in int_detail:
            status = "PASS" if r["pass"] else "FAIL"
            prompt = r["prompt"][:35]
            fail = r["failure"][:40] if r["failure"] else ""
            w(f"| {r['id']} | {r['level']} | {prompt} | {status} | {r['iters']} | {r['time_s']}s | {r['files']} | {fail} |")
        w(f"")

        # Tool sequences for each build
        w(f"### Tool Sequences")
        w(f"")
        for r in int_detail:
            status = "PASS" if r["pass"] else "FAIL"
            seq = " -> ".join(r["tools"][:15])
            if len(r["tools"]) > 15:
                seq += f" ... ({len(r['tools'])} total)"
            w(f"- **{r['id']}** [{status}]: `{seq}`")
        w(f"")

        # Diagnostics
        diags = d.get("diagnostics", {})
        w(f"### Agentic Diagnostics")
        w(f"")
        w(f"| Metric | Value | Status |")
        w(f"|--------|-------|--------|")
        for key in ["path_errors", "shell_loops", "edit_failures", "missing_qa", "build_fail_rate"]:
            val = diags.get(key, 0)
            if key == "build_fail_rate":
                bad = val != "0%"
            elif key == "missing_qa":
                bad = val > len(int_detail) // 2
            else:
                bad = val > 0
            status = "BAD" if bad else "OK"
            w(f"| {key} | {val} | {status} |")
        w(f"")

        # Per-build diagnostics detail
        has_issues = [r for r in int_detail if r.get("diagnostics")]
        if has_issues:
            w(f"### Per-Build Diagnostics")
            w(f"")
            for r in has_issues:
                diag = r["diagnostics"]
                issues = []
                if diag.get("path_errors"): issues.append(f"path_errors={diag['path_errors']}")
                if diag.get("shell_exec_loops"): issues.append(f"shell_loops={diag['shell_exec_loops']}")
                if diag.get("edit_failures"): issues.append(f"edit_fails={diag['edit_failures']}")
                if diag.get("missing_qa"): issues.append("missing_qa")
                if diag.get("stalls"): issues.append(f"stalls={diag['stalls']}")
                if diag.get("build_failures"):
                    issues.append(f"build_fail={diag['build_failures']}/{diag.get('build_attempts', '?')}")
                features = []
                if diag.get("used_plan"): features.append("plan")
                if diag.get("used_swell"): features.append("swell")
                if diag.get("used_undertow"): features.append("undertow")
                if diag.get("used_search"): features.append("search")

                status = "PASS" if r["pass"] else "FAIL"
                issue_str = ", ".join(issues) if issues else "clean"
                feat_str = ", ".join(features) if features else "basic"
                w(f"- **{r['id']}** [{status}] issues=[{issue_str}] features=[{feat_str}]")
            w(f"")

        # Failure analysis
        fails = d.get("failures", [])
        if fails:
            w(f"### Failure Analysis")
            w(f"")
            for f in fails:
                w(f"- **{f['id']}**: {f['mode']}")
            w(f"")

    # --- COMPARISON ---
    if prev:
        w(f"## Comparison vs Previous")
        w(f"")
        w(f"**Previous run**: {prev.get('timestamp', 'unknown')}")
        w(f"")
        w(f"| Layer | Before | After | Delta |")
        w(f"|-------|--------|-------|-------|")
        for layer in layer_order:
            if layer in report and layer in prev:
                curr = report[layer]["passed"]
                prev_v = prev[layer]["passed"]
                total = report[layer]["total"]
                diff = curr - prev_v
                arrow = "+" if diff > 0 else "" if diff < 0 else ""
                w(f"| {layer} | {prev_v}/{total} | {curr}/{total} | {arrow}{diff} |")
        w(f"")

    # --- TRAINING DATA SIGNALS ---
    # Extract actionable signals for training data improvement
    signals = []
    if format_detail:
        wrong_tool = [r for r in format_detail if r["pass"] and not r["correct"]]
        if wrong_tool:
            signals.append(f"L1: {len(wrong_tool)} prompts got a tool call but wrong tool — add training examples for these")
        no_tool = [r for r in format_detail if not r["pass"]]
        if no_tool:
            signals.append(f"L1: {len(no_tool)} prompts produced no tool call — model not triggering on these prompt patterns")

    if hackfree_detail:
        still = [r for r in hackfree_detail if r["status"] == "FAIL"]
        for r in still:
            signals.append(f"L4: Hack still needed: {r['hack']} — add training examples for {r['desc']}")

    if int_detail:
        for r in int_detail:
            if not r["pass"] and r["failure"]:
                signals.append(f"L5: {r['id']} failed: {r['failure'][:80]}")
            diag = r.get("diagnostics", {})
            if diag.get("shell_exec_loops", 0) >= 2:
                signals.append(f"L5: {r['id']} shell loop — add rewrite-after-error examples")
            if diag.get("edit_failures", 0) > 0:
                signals.append(f"L5: {r['id']} edit hallucination — train on file_write instead of file_edit after errors")
            if diag.get("path_errors", 0) > 0:
                signals.append(f"L5: {r['id']} path errors — standardize to cd deliverables/X in training data")

    if signals:
        w(f"## Training Data Signals")
        w(f"")
        w(f"Actions to improve the next training round:")
        w(f"")
        for s in signals:
            w(f"- {s}")
        w(f"")

    w(f"---")
    w(f"*Generated by eval_all.py*")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="Full eval pyramid")
    parser.add_argument("--endpoint", default="http://localhost:8095")
    parser.add_argument("--quick", action="store_true", help="Skip integration eval")
    parser.add_argument("--layers", default=None,
                        help="Comma-separated: format,scaffold,recovery,hackfree,integration")
    parser.add_argument("--output", default="workspace/training_data/eval_report.json")
    parser.add_argument("--compare", default=None, help="Previous report JSON to compare against")
    args = parser.parse_args()

    layers = set()
    if args.layers:
        layers = set(args.layers.split(","))
    elif args.quick:
        layers = {"format", "scaffold", "recovery", "hackfree"}
    else:
        layers = {"format", "scaffold", "recovery", "hackfree", "integration"}

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "endpoint": args.endpoint,
        "layers_run": sorted(layers),
    }
    t0 = time.monotonic()

    # Keep per-test details for the report
    format_detail = []
    scaffold_detail = []
    recovery_detail = []
    hackfree_detail = []
    int_detail = []

    # Layer 1: Format
    if "format" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 1: FORMAT EVAL")
        print(f"{'='*60}")
        from eval_toolcall import eval_format, EVAL_PROMPTS
        format_results = await eval_format(args.endpoint, EVAL_PROMPTS)
        n = len(format_results)
        passed = sum(1 for r in format_results if r.produced_tool_call)
        report["format"] = {
            "total": n, "passed": passed,
            "pct": f"{100*passed/n:.0f}%",
            "valid_name": sum(1 for r in format_results if r.valid_tool_name),
            "correct_first": sum(1 for r in format_results if r.first_tool_correct),
        }
        format_detail = [
            {"id": r.prompt_id, "level": r.level, "prompt": r.prompt,
             "pass": r.produced_tool_call, "tool": r.first_tool or "NONE",
             "expected": r.expected_first_tool, "correct": r.first_tool_correct,
             "latency_ms": round(r.latency_ms), "error": r.error}
            for r in format_results
        ]

    # Layer 2: Scaffold Selection
    if "scaffold" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 2: SCAFFOLD SELECTION")
        print(f"{'='*60}")
        from eval_scaffold_selection import eval_scaffolds
        scaffold_results = await eval_scaffolds(args.endpoint)
        n = len(scaffold_results)
        passed = sum(1 for r in scaffold_results if r["status"] == "PASS")
        report["scaffold"] = {"total": n, "passed": passed, "pct": f"{100*passed/n:.0f}%"}
        scaffold_detail = scaffold_results

    # Layer 3: Error Recovery
    if "recovery" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 3: ERROR RECOVERY")
        print(f"{'='*60}")
        from eval_error_recovery import eval_recovery
        recovery_results = await eval_recovery(args.endpoint)
        n = len(recovery_results)
        passed = sum(1 for r in recovery_results if r["status"] == "PASS")
        report["recovery"] = {"total": n, "passed": passed, "pct": f"{100*passed/n:.0f}%"}
        recovery_detail = recovery_results

    # Layer 4: Hack-Free
    if "hackfree" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 4: HACK-FREE BEHAVIOR")
        print(f"{'='*60}")
        from eval_hack_free import eval_hack_free
        hackfree_results = await eval_hack_free(args.endpoint)
        n = len(hackfree_results)
        passed = sum(1 for r in hackfree_results if r["status"] == "PASS")
        report["hackfree"] = {
            "total": n, "passed": passed, "pct": f"{100*passed/n:.0f}%",
            "still_needs_hacks": [r["hack"] for r in hackfree_results if r["status"] == "FAIL"],
        }
        hackfree_detail = hackfree_results

    # Layer 5: Integration
    if "integration" in layers:
        print(f"\n{'='*60}")
        print(f"  LAYER 5: INTEGRATION (real builds)")
        print(f"{'='*60}")
        from eval_integration import run_agent_build, EVAL_PROMPTS as INT_PROMPTS
        int_results = []
        for p in INT_PROMPTS:
            log.info(f"  Building: {p['prompt'][:50]}...")
            r = await run_agent_build(args.endpoint, p["prompt"], timeout=180)
            r.prompt_id = p["id"]
            r.level = p["level"]
            int_results.append(r)
            status = "PASS" if r.delivered and r.compiled else "FAIL"
            log.info(f"    {status} | {r.iterations} iters | {r.wall_clock_s:.0f}s | {r.failure_mode or 'OK'}")

        n = len(int_results)
        passed = sum(1 for r in int_results if r.delivered and r.compiled)
        report["integration"] = {
            "total": n, "passed": passed, "pct": f"{100*passed/n:.0f}%",
            "avg_iters": round(sum(r.iterations for r in int_results) / n, 1),
            "avg_time_s": round(sum(r.wall_clock_s for r in int_results) / n, 1),
            "diagnostics": {
                "path_errors": sum(r.diagnostics.get("path_errors", 0) for r in int_results),
                "shell_loops": sum(r.diagnostics.get("shell_exec_loops", 0) for r in int_results),
                "edit_failures": sum(r.diagnostics.get("edit_failures", 0) for r in int_results),
                "missing_qa": sum(1 for r in int_results if r.diagnostics.get("missing_qa")),
                "build_fail_rate": f"{100*sum(r.diagnostics.get('build_failures',0) for r in int_results)/max(sum(r.diagnostics.get('build_attempts',0) for r in int_results),1):.0f}%",
            },
            "failures": [
                {"id": r.prompt_id, "mode": r.failure_mode}
                for r in int_results if not (r.delivered and r.compiled)
            ],
        }
        int_detail = [
            {"id": r.prompt_id, "level": r.level, "prompt": r.prompt,
             "pass": r.delivered and r.compiled,
             "scaffolded": r.scaffolded, "files": r.files_written,
             "compiled": r.compiled, "delivered": r.delivered,
             "iters": r.iterations, "time_s": round(r.wall_clock_s, 1),
             "failure": r.failure_mode or "",
             "tools": r.tool_sequence[:20],
             "diagnostics": r.diagnostics}
            for r in int_results
        ]

    elapsed = time.monotonic() - t0
    report["elapsed_s"] = round(elapsed, 1)

    # Load previous run for comparison
    prev = None
    if args.compare and Path(args.compare).exists():
        with open(args.compare) as f:
            prev = json.load(f)

    # === CONSOLE SUMMARY ===
    print(f"\n{'='*60}")
    print(f"  TSUNAMI EVAL REPORT")
    print(f"  {report['timestamp']} | {elapsed:.0f}s")
    print(f"{'='*60}\n")

    layer_order = ["format", "scaffold", "recovery", "hackfree", "integration"]
    for layer in layer_order:
        if layer in report:
            data = report[layer]
            p = data["passed"]
            t = data["total"]
            pct = data["pct"]
            bar = "█" * (p * 20 // t) + "░" * (20 - p * 20 // t)
            delta_str = ""
            if prev and layer in prev:
                d = p - prev[layer]["passed"]
                if d != 0:
                    delta_str = f"  \033[{'32' if d > 0 else '31'}m{'↑' if d > 0 else '↓'}{'+' if d > 0 else ''}{d}\033[0m"
            print(f"  {layer:<13} {bar} {p}/{t} ({pct}){delta_str}")

    # === GENERATE MARKDOWN REPORT ===
    md = generate_markdown_report(
        report, prev, format_detail, scaffold_detail,
        recovery_detail, hackfree_detail, int_detail,
    )

    # Save JSON
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Save per-test details in JSON (for future comparisons)
    detail_data = {**report, "details": {
        "format": format_detail, "scaffold": scaffold_detail,
        "recovery": recovery_detail, "hackfree": hackfree_detail,
        "integration": int_detail,
    }}
    detail_path = args.output.replace(".json", "_detail.json")
    with open(detail_path, "w") as f:
        json.dump(detail_data, f, indent=2, default=str)

    # Save markdown report
    report_path = args.output.replace(".json", ".md")
    with open(report_path, "w") as f:
        f.write(md)

    log.info(f"\n  JSON:   {args.output}")
    log.info(f"  Detail: {detail_path}")
    log.info(f"  Report: {report_path}")
    log.info(f"  Compare next time with: --compare {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
