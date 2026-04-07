#!/usr/bin/env python3
"""Print eval summary for GitHub Actions step summary or terminal.

Reads the JSON report(s) and prints a compact markdown summary.
Supports both the old split format (eval_quick_report.json / eval_l5_report.json)
and the new unified format (eval_report.json).
"""
import json
import sys
from pathlib import Path


def print_scoreboard(report):
    """Print the layer scoreboard."""
    layers = ["format", "scaffold", "recovery", "hackfree", "integration"]
    print("| Layer | Score | Pct |")
    print("|-------|-------|-----|")
    for layer in layers:
        if layer not in report:
            continue
        d = report[layer]
        print(f"| {layer} | {d['passed']}/{d['total']} | {d['pct']} |")
    print()


def print_failures(report):
    """Print failure details."""
    # Hack-free failures
    if "hackfree" in report:
        hacks = report["hackfree"].get("still_needs_hacks", [])
        if hacks:
            print("**Still needs hacks:**")
            for h in hacks:
                print(f"- {h}")
            print()

    # Integration failures
    if "integration" in report:
        failures = report["integration"].get("failures", [])
        if failures:
            print("**Integration failures:**")
            for f in failures:
                print(f"- {f['id']}: {f['mode']}")
            print()

        diags = report["integration"].get("diagnostics", {})
        bad = {k: v for k, v in diags.items() if v and v != "0%" and v != 0}
        if bad:
            print("**Diagnostics:**")
            for k, v in bad.items():
                print(f"- {k}: {v}")
            print()


def main():
    # Try unified report first
    unified = Path("eval_report.json")
    if not unified.exists():
        unified = Path("workspace/training_data/eval_report.json")

    if unified.exists():
        report = json.loads(unified.read_text())
        ts = report.get("timestamp", "unknown")
        elapsed = report.get("elapsed_s", 0)
        print(f"**{ts}** | {elapsed:.0f}s\n")
        print_scoreboard(report)
        print_failures(report)
        return

    # Fall back to old split format
    print("```")
    for report_file in ["eval_quick_report.json", "eval_l5_report.json"]:
        p = Path(report_file)
        if not p.exists():
            continue
        r = json.loads(p.read_text())

        if "format" in r:
            for layer in ["format", "scaffold", "recovery", "hackfree"]:
                if layer in r:
                    d = r[layer]
                    print(f"{layer:>12}: {d['passed']}/{d['total']} ({d['pct']})")

        if "results" in r:
            results = r["results"]
            passed = sum(1 for x in results if x.get("delivered") and x.get("compiled"))
            total = len(results)
            print(f"{'integration':>12}: {passed}/{total} ({100*passed//max(total,1)}%)")
            for x in results:
                status = "PASS" if x.get("delivered") and x.get("compiled") else "FAIL"
                iters = x.get("iterations", 0)
                secs = x.get("wall_clock_s", 0)
                mode = x.get("failure_mode", "OK")
                print(f"  {x.get('id','?')} [{status}] {iters} iters {secs:.0f}s {mode}")
    print("```")


if __name__ == "__main__":
    main()
