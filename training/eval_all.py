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
from pathlib import Path

# Fix imports — add training/ to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("eval_all")


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

    elapsed = time.monotonic() - t0
    report["elapsed_s"] = round(elapsed, 1)

    # === FINAL REPORT ===
    print(f"\n{'='*60}")
    print(f"  TSUNAMI EVAL REPORT")
    print(f"  {report['timestamp']} | {elapsed:.0f}s")
    print(f"{'='*60}\n")

    layer_order = ["format", "scaffold", "recovery", "hackfree", "integration"]
    for layer in layer_order:
        if layer in report:
            data = report[layer]
            passed = data["passed"]
            total = data["total"]
            pct = data["pct"]
            bar = "█" * (passed * 20 // total) + "░" * (20 - passed * 20 // total)
            print(f"  {layer:<13} {bar} {passed}/{total} ({pct})")

            # Show failures for hackfree
            if layer == "hackfree" and data.get("still_needs_hacks"):
                for hack in data["still_needs_hacks"]:
                    print(f"    ⚠ {hack}")

            # Show diagnostics for integration
            if layer == "integration":
                diags = data.get("diagnostics", {})
                bad = {k: v for k, v in diags.items() if v and v != "0%"}
                if bad:
                    for k, v in bad.items():
                        print(f"    ⚠ {k}: {v}")

    # === COMPARE TO PREVIOUS ===
    if args.compare and Path(args.compare).exists():
        print(f"\n{'='*60}")
        print(f"  COMPARISON vs {args.compare}")
        print(f"{'='*60}\n")
        with open(args.compare) as f:
            prev = json.load(f)

        for layer in layer_order:
            if layer in report and layer in prev:
                curr = report[layer]["passed"]
                prev_v = prev[layer]["passed"]
                total = report[layer]["total"]
                delta = curr - prev_v
                arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
                color = "\033[32m" if delta > 0 else "\033[31m" if delta < 0 else "\033[33m"
                print(f"  {layer:<13} {prev_v}/{total} → {curr}/{total}  {color}{arrow} {'+' if delta > 0 else ''}{delta}\033[0m")

    # Save
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"\n  Saved to {args.output}")
    log.info(f"  Compare next time with: --compare {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
