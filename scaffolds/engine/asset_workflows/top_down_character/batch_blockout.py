"""Batch runner over corpus blockout specs.

Walks `scaffolds/.claude/blockouts/<essence>/*.json` for a filtered set
and fires `run_blockout.py`-equivalent for each. Idempotent — already-
produced blockout sheets are skipped. Useful for validating a whole
essence's character roster in one command.

Usage:
    # Dry-run — print plan for all of Dragon Quest's 16 specs
    python3 batch_blockout.py --essence 1986_dragon_quest

    # Live-fire Dragon Quest's 6-armor hero progression only
    python3 batch_blockout.py --essence 1986_dragon_quest --name-match hero_ --apply

    # All corpus specs (30 characters)
    python3 batch_blockout.py --apply --model-kind Turbo

    # Limit for budget control
    python3 batch_blockout.py --essence 1986_dragon_quest --apply --limit 3
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent / "_common"))
sys.path.insert(0, str(_HERE))

from blockout_loader import list_blockouts  # noqa: E402
from run_blockout import _fire_ernie_direction, _seed_int  # noqa: E402
from blockout_loader import blockout_prompts, blockout_seed  # noqa: E402
from postprocess import assemble_from_corpus  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--essence", type=str, help="filter to one essence")
    ap.add_argument("--projection", type=str, default="top_down",
                    choices=["top_down", "iso"],
                    help="which projection's specs to run (default top_down)")
    ap.add_argument("--name-match", type=str, default=None,
                    help="substring filter on animation_name (e.g. hero_)")
    ap.add_argument("--out", type=Path, default=Path("./out/blockouts"))
    ap.add_argument("--model-kind", default="Turbo", choices=["Turbo", "Base"])
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

    print(f"Matched {len(specs)} blockout spec(s)")
    for s in specs:
        print(f"  {s['essence']}/{s['animation_name']} ({s['rotation_angles']}-dir)")

    if not specs:
        print("Nothing to do.")
        return 0

    if not args.apply:
        print(f"\nDRY-RUN — run with --apply to fire ERNIE.")
        print(f"Budget estimate: {sum(len(s['directions']) for s in specs)} ERNIE calls "
              f"(~{'17s' if args.model_kind == 'Turbo' else '4min'}/call)")
        return 0

    t0 = time.time()
    dispositions = {"assembled": 0, "cached": 0, "error": 0}
    for i, raw in enumerate(specs, 1):
        essence = raw["essence"]
        animation_name = raw["animation_name"]
        target_dir = args.out / essence / animation_name
        sheet = target_dir / f"{essence}_{animation_name}_movement_blockout.png"

        # Idempotent resume
        if sheet.exists():
            print(f"[{i}/{len(specs)}] {essence}/{animation_name} — cached")
            dispositions["cached"] += 1
            continue

        print(f"\n[{i}/{len(specs)}] {essence}/{animation_name} — firing...")
        target_dir.mkdir(parents=True, exist_ok=True)
        prompts = blockout_prompts(raw)
        seed_label = blockout_seed(raw)
        direction_to_frame: dict[str, Path] = {}
        try:
            for d in raw["directions"]:
                dest = target_dir / f"frame_{d}.png"
                if dest.exists():
                    direction_to_frame[d] = dest
                    continue
                print(f"  [{d}] ERNIE {args.model_kind}...", end=" ", flush=True)
                t_dir = time.time()
                _fire_ernie_direction(prompts[d], seed_label, dest,
                                      model_kind=args.model_kind)
                direction_to_frame[d] = dest
                print(f"{time.time()-t_dir:.1f}s")
            print(f"  assembling...")
            assemble_from_corpus(
                essence=essence, animation_name=animation_name,
                direction_to_frame=direction_to_frame, out_dir=target_dir,
            )
            dispositions["assembled"] += 1
        except SystemExit as e:
            print(f"  ERROR: {e}")
            dispositions["error"] += 1
            # ERNIE unreachable etc. — don't loop through the remaining specs
            break

    elapsed = time.time() - t0
    print(f"\n=== batch done in {elapsed:.0f}s ===")
    for k, v in dispositions.items():
        print(f"  {k}: {v}")
    return 0 if dispositions["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
