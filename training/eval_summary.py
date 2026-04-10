#!/usr/bin/env python3
"""Print eval summary in markdown for GitHub Actions step summary."""
import json
from pathlib import Path

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
