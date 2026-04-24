"""Batch runner over the nudge corpus.

Walks `scaffolds/.claude/nudges/<essence>/*.json`, filters by quality +
kind + essence, and calls `base_plus_chain.run_payload` for each. Resume
is automatic — already-produced outputs are `cached` dispositions.

Ordering: parsed-with-nudges first (gold), then static ERNIE-only, then
unparsed-needs-animation (skipped unless `--include-unparsed`). This
gives you the proven cases before spending cycles on best-guess ones.

Usage:
    # dry-run over all gold animations
    python3 batch_run.py --dry-run

    # live fire, gold-only (22 animations ≈ 3 hr budget)
    python3 batch_run.py --apply --min-nudges 3

    # only one essence, static+animated
    python3 batch_run.py --apply --essence 1981_galaga

    # rate-limit: max 10 payloads per run
    python3 batch_run.py --apply --limit 10
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from base_plus_chain import run_payload

CLAUDE_ROOT = Path(__file__).parent.parent.parent.parent / ".claude"
NUDGES_DIR = CLAUDE_ROOT / "nudges"


def _load_payloads() -> list[dict]:
    """Load every nudge JSON in the corpus. Returns list of (payload,
    path) tuples tagged with _path for debug."""
    out: list[dict] = []
    if not NUDGES_DIR.is_dir():
        print(f"ERROR: {NUDGES_DIR} not found", file=sys.stderr)
        return []
    for ed in sorted(NUDGES_DIR.iterdir()):
        if not ed.is_dir():
            continue
        for f in sorted(ed.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                data["_path"] = str(f)
                out.append(data)
            except Exception:
                continue
    return out


def _priority_key(payload: dict) -> tuple:
    """Rank: parsed-animated first (gold), then static, then unparsed-
    animated (last). Within each bucket, sort by essence + name for
    determinism."""
    needs = payload.get("needs_animation", False)
    nudge_count = len(payload.get("nudges", []))
    if needs and nudge_count >= 3:
        tier = 0  # gold chain
    elif needs and nudge_count > 0:
        tier = 1  # parsed but short chain
    elif not needs:
        tier = 2  # static ERNIE-only
    else:
        tier = 3  # needs animation but no parsed nudges
    return (tier, payload.get("essence", ""), payload.get("animation_name", ""))


def _filter_payloads(
    payloads: list[dict],
    essence: str | None,
    kind: str | None,
    sub_kind: str | None,
    min_nudges: int,
    max_nudges: int | None,
    include_unparsed: bool,
    include_static: bool,
) -> list[dict]:
    filtered = []
    for p in payloads:
        if essence and p.get("essence") != essence:
            continue
        if kind and p.get("kind") != kind:
            continue
        if sub_kind and p.get("sub_kind") != sub_kind:
            continue
        nc = len(p.get("nudges", []))
        needs = p.get("needs_animation", False)
        if needs:
            if nc < min_nudges:
                if not include_unparsed or nc > 0:
                    continue
            if max_nudges is not None and nc > max_nudges:
                continue
        else:
            if not include_static:
                continue
        filtered.append(p)
    return filtered


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("./out/bpc"),
                    help="output directory")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="actually fire ERNIE + Qwen")
    g.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--essence", type=str, help="filter to one essence (e.g. 1981_galaga)")
    ap.add_argument("--kind", type=str, help="filter by top-level kind (e.g. effect_layer)")
    ap.add_argument("--sub-kind", type=str, help="filter by sub_kind (e.g. explosion_vfx)")
    ap.add_argument("--min-nudges", type=int, default=0,
                    help="minimum nudges to qualify (0=include static; 3=gold-only)")
    ap.add_argument("--max-nudges", type=int, default=None,
                    help="maximum nudges (useful to cap chain-length for budget)")
    ap.add_argument("--include-unparsed", action="store_true",
                    help="include multi-frame animations with 0 parsed nudges")
    ap.add_argument("--no-static", action="store_true",
                    help="exclude static (no Qwen needed) payloads")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap at N payloads per run")
    ap.add_argument("--sleep-between", type=float, default=0.0,
                    help="sleep seconds between payloads (rate-limit)")
    args = ap.parse_args()

    payloads = _load_payloads()
    print(f"Loaded {len(payloads)} nudge payloads from corpus")

    filtered = _filter_payloads(
        payloads,
        essence=args.essence, kind=args.kind, sub_kind=args.sub_kind,
        min_nudges=args.min_nudges, max_nudges=args.max_nudges,
        include_unparsed=args.include_unparsed,
        include_static=not args.no_static,
    )
    filtered.sort(key=_priority_key)
    if args.limit:
        filtered = filtered[:args.limit]
    print(f"Filtered to {len(filtered)} payloads after filters:")
    tiers = Counter()
    for p in filtered:
        if p.get("needs_animation", False):
            nc = len(p.get("nudges", []))
            tiers["animated_gold" if nc >= 3 else "animated_partial" if nc > 0 else "animated_unparsed"] += 1
        else:
            tiers["static"] += 1
    for tier, n in tiers.most_common():
        print(f"  {tier}: {n}")
    print()

    dispositions: Counter = Counter()
    errors: list[str] = []
    t0 = time.time()
    for i, payload in enumerate(filtered, 1):
        print(f"[{i}/{len(filtered)}] {payload['essence']}/{payload['animation_name']}")
        result = run_payload(payload, args.out, dry_run=not args.apply)
        dispositions[result.disposition] += 1
        if result.error:
            errors.append(f"{result.payload_id}: {result.error}")
            print(f"  ERROR: {result.error}")
        if args.sleep_between > 0 and args.apply and i < len(filtered):
            time.sleep(args.sleep_between)

    elapsed = time.time() - t0
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"\n=== {mode} complete ===")
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Dispositions:")
    for d, n in dispositions.most_common():
        print(f"  {d}: {n}")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:5]:
            print(f"  {e}")
        if len(errors) > 5:
            print(f"  ... +{len(errors)-5} more")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
