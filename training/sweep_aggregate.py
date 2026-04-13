#!/usr/bin/env python3
"""Aggregate sweep results and rank by composite pyramid score.

Reads every JSON in workspace/training_data/sweep/ and produces a ranked table.
Composite score = sum(layer_pct) weighted by layer importance.
"""
import json
from pathlib import Path

SWEEP_DIR = Path("workspace/training_data/sweep")
ADAPTER_DIR = Path("models/sweep")

# Weights reflect "which layer matters most for production." L5 is the real test;
# L1 is cheap format-check. Tune these if you want a different ordering.
WEIGHTS = {
    "format":      1.0,
    "scaffold":    1.5,
    "recovery":    2.0,
    "hackfree":    2.0,
    "integration": 3.0,
}


def pct(d: dict, key: str) -> float:
    r = d.get(key, {})
    total = r.get("total", 0)
    passed = r.get("passed", 0)
    return (100.0 * passed / total) if total else 0.0


def main():
    if not SWEEP_DIR.exists():
        print(f"No sweep results at {SWEEP_DIR}")
        return

    rows = []
    for jf in sorted(SWEEP_DIR.glob("*.json")):
        try:
            d = json.loads(jf.read_text())
        except Exception as e:
            print(f"skip {jf.name}: {e}")
            continue
        layers = {k: pct(d, k) for k in WEIGHTS}
        composite = sum(layers[k] * w for k, w in WEIGHTS.items()) / sum(WEIGHTS.values())
        rows.append({"name": jf.stem, **layers, "composite": composite})

    if not rows:
        print("No valid sweep results.")
        return

    rows.sort(key=lambda r: r["composite"], reverse=True)

    header = f"{'rank':<4} {'name':<22} {'fmt':>5} {'scf':>5} {'rec':>5} {'hkf':>5} {'int':>5} {'composite':>10}"
    sep = "-" * 72
    lines = [header, sep]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"{i:<4} {r['name']:<22} "
            f"{r['format']:>5.1f} {r['scaffold']:>5.1f} {r['recovery']:>5.1f} "
            f"{r['hackfree']:>5.1f} {r['integration']:>5.1f} "
            f"{r['composite']:>10.2f}"
        )
    table = "\n".join(lines)
    print()
    print(table)

    winner = rows[0]
    adapter = ADAPTER_DIR / f"{winner['name']}-merged"
    train_log = Path("training/logs/sweep") / f"{winner['name']}.log"
    summary = [
        "",
        f"WINNER: {winner['name']} (composite {winner['composite']:.2f})",
        f"  Adapter: {adapter}" + ("" if adapter.exists() else "  (missing)"),
        f"  Train log: {train_log}" + ("" if train_log.exists() else "  (missing)"),
        f"  Eval JSON: workspace/training_data/sweep/{winner['name']}.json",
        "",
        "To promote:",
        f"  cp -r {adapter} models/tsunami-adapter-champion-merged",
    ]
    print("\n".join(summary))

    # Persist a clean scores.md so you can grep it / scp it off the pod.
    scores_md = SWEEP_DIR / "SCORES.md"
    scores_md.write_text(
        "# Sweep scores\n\n"
        f"Generated: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}\n\n"
        "Layer weights: "
        + ", ".join(f"{k}={v}" for k, v in WEIGHTS.items())
        + "\n\n```\n"
        + table
        + "\n```\n\n"
        + "\n".join(summary)
        + "\n\n## Per-sweep artifacts\n\n"
        + "\n".join(
            f"- **{r['name']}** — "
            f"log: `training/logs/sweep/{r['name']}.log` · "
            f"eval: `workspace/training_data/sweep/{r['name']}.json` · "
            f"adapter: `models/sweep/{r['name']}-merged`"
            for r in rows
        )
        + "\n"
    )
    print(f"\nScores written to: {scores_md}")


if __name__ == "__main__":
    main()
