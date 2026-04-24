"""Roster runner — chain `make_character.py` over every corpus spec
for an essence (or filtered subset). Fires the full 3-phase pipeline
per character with idempotent resume.

Where `batch_blockout.py` stops at phase 1 (blockout only),
`make_roster.py` runs all 3 phases per character (blockout →
animation → strip).

Usage:
    # Dry-run — print plan for all Dragon Quest characters
    python3 make_roster.py --essence 1986_dragon_quest

    # Live-fire Dragon Quest hero 6-armor progression
    python3 make_roster.py --essence 1986_dragon_quest --name-match hero_ --apply

    # Full Dragon Quest roster (16 chars, ~40 min Turbo)
    python3 make_roster.py --essence 1986_dragon_quest --apply

    # Only phase 1 (skip animation + strip)
    python3 make_roster.py --essence 1986_dragon_quest --apply --no-animation --no-strip

    # Every corpus character across all essences
    python3 make_roster.py --apply
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent / "_common"))

from blockout_loader import list_blockouts  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--essence", type=str, help="filter to one essence")
    ap.add_argument("--projection", type=str, default="top_down",
                    choices=["top_down", "iso"])
    ap.add_argument("--name-match", type=str, default=None,
                    help="substring filter on animation_name")
    ap.add_argument("--anim", default="walk",
                    help="anim for phase 2 (default walk)")
    ap.add_argument("--out", type=Path, default=Path("./out/blockouts"))
    ap.add_argument("--model-kind", default="Turbo", choices=["Turbo", "Base"])
    ap.add_argument("--no-animation", action="store_true")
    ap.add_argument("--no-strip", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()

    specs = list_blockouts(projection=args.projection)
    if args.essence:
        specs = [s for s in specs if s["essence"] == args.essence]
    if args.name_match:
        specs = [s for s in specs if args.name_match in s["animation_name"]]
    specs.sort(key=lambda s: (s["essence"], s["animation_name"]))
    if args.limit:
        specs = specs[: args.limit]

    print(f"Matched {len(specs)} spec(s)")
    for s in specs:
        walk = s.get("anim_frame_targets", {}).get(args.anim)
        tag = f"(+{args.anim} {walk}f)" if walk else "(blockout only)"
        print(f"  {s['essence']}/{s['animation_name']}  {tag}")

    if not specs:
        print("Nothing to do.")
        return 0

    # Rough budget estimate
    ernie_calls = sum(len(s["directions"]) for s in specs)
    qwen_calls = 0 if args.no_animation else sum(
        (s.get("anim_frame_targets", {}).get(args.anim, 0) - 1) * len(s["directions"])
        for s in specs
    )
    ernie_min = ernie_calls * (17 if args.model_kind == "Turbo" else 240) / 60
    qwen_min = qwen_calls * 80 / 60  # 80s/frame @ 20-step karras
    total_min = ernie_min + qwen_min
    print(f"\nBudget: {ernie_calls} ERNIE + {qwen_calls} Qwen calls ≈ {total_min:.0f} min")

    if not args.apply:
        print(f"\nDRY-RUN — pass --apply to execute.")
        return 0

    t0 = time.time()
    dispositions = {"ok": 0, "skipped": 0, "error": 0}
    for i, s in enumerate(specs, 1):
        essence = s["essence"]
        anim_name = s["animation_name"]
        print(f"\n[{i}/{len(specs)}] {essence}/{anim_name}")
        cmd = [
            "python3", "make_character.py",
            essence, anim_name,
            "--apply",
            "--model-kind", args.model_kind,
            "--anim", args.anim,
            "--out", str(args.out),
        ]
        if args.no_animation:
            cmd.append("--no-animation")
        if args.no_strip:
            cmd.append("--no-strip")
        rc = subprocess.call(cmd, cwd=str(_HERE))
        if rc == 0:
            dispositions["ok"] += 1
        else:
            dispositions["error"] += 1
            print(f"  stopping roster on error ({rc})", file=sys.stderr)
            break

    elapsed = time.time() - t0
    print(f"\n=== roster done in {elapsed:.0f}s ===")
    for k, v in dispositions.items():
        print(f"  {k}: {v}")
    return 0 if dispositions["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
