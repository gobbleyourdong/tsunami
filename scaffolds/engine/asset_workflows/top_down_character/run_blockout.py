"""Driver: fire a corpus-driven character blockout end-to-end.

Loads one harvested blockout spec from
`scaffolds/.claude/blockouts/<essence>/<animation_name>.json`, fires
ERNIE once per direction with a pinned shared seed, then postprocesses
via `assemble_from_corpus` into a blockout sheet + manifest.

Usage (dry-run — no server calls):
    python3 run_blockout.py 1986_dragon_quest hero_plainclothes_walk

Live fire (requires ERNIE :8092 Turbo or Base):
    python3 run_blockout.py 1986_dragon_quest hero_plainclothes_walk --apply

    # Cheaper Turbo model (8-step, ~17s/direction vs Base 50-step ~4min)
    python3 run_blockout.py 1986_dragon_quest hero_plainclothes_walk --apply --model-kind Turbo

    # Custom output dir (default ./out/blockouts/)
    python3 run_blockout.py 1986_dragon_quest hero_plainclothes_walk --apply --out ./tmp/dq

Dragon Quest 6-armor-tier batch (when ERNIE is back):
    for anim in hero_plainclothes_walk hero_leather_armor_walk hero_chain_armor_walk \
                hero_half_plate_walk hero_full_plate_walk hero_magic_armor_walk; do
        python3 run_blockout.py 1986_dragon_quest "$anim" --apply
    done

Output (per run):
    ./out/blockouts/<essence>/<anim>/
        frame_N.png, frame_E.png, frame_S.png, frame_W.png
        <essence>_<anim>_movement_blockout.png           ← the 4×1 sheet
        <essence>_<anim>_movement_blockout.manifest.json ← cell coords
        <essence>_<anim>_movement_blockout.spec.json     ← provenance + anim_frame_targets
        <essence>_<anim>_movement_blockout_preview.png   ← dev-view labeled grid
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

try:
    import requests  # type: ignore
except ImportError:
    requests = None

# Wire up the sibling modules
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent / "_common"))
sys.path.insert(0, str(_HERE))

from blockout_loader import load_blockout, blockout_prompts, blockout_seed  # noqa: E402
from postprocess import assemble_from_corpus  # noqa: E402

ERNIE_URL = os.environ.get("ERNIE_URL", "http://localhost:8092")


def _seed_int(label: str, salt: str = "") -> int:
    return int(hashlib.sha256((label + salt).encode()).hexdigest()[:8], 16)


def _fire_ernie_direction(
    prompt: str, seed_label: str, save_path: Path,
    model_kind: str = "Turbo",
) -> None:
    if requests is None:
        raise SystemExit("requests not installed")
    steps = 50 if model_kind == "Base" else 8
    body = {
        "prompt": prompt,
        "negative_prompt": "text, words, UI, HUD, 3D rendering, anti-aliasing, drop shadow, multiple characters",
        "height": 1024,
        "width": 1024,
        "num_inference_steps": steps,
        "guidance_scale": 4.0,
        "seed": _seed_int(seed_label),  # SAME seed across all N directions
        "n": 1,
        "response_format": "save_path",
        "save_path": str(save_path.absolute()),
        "use_pe": False,
        "model_kind": model_kind,
    }
    try:
        r = requests.post(f"{ERNIE_URL}/v1/images/generate", json=body, timeout=600)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise SystemExit(
            f"ERNIE not reachable at {ERNIE_URL}. Bring it up first:\n"
            f"  python -m tsunami.serving.ernie_server --model {model_kind} --port 8092"
        )
    except requests.exceptions.HTTPError:
        raise SystemExit(f"ERNIE returned {r.status_code}: {r.text[:200]}")
    if not save_path.exists():
        raise SystemExit(f"ERNIE claimed success but {save_path} missing")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("essence", help="e.g. 1986_dragon_quest")
    ap.add_argument("animation_name", help="e.g. hero_plainclothes_walk")
    ap.add_argument("--out", type=Path, default=Path("./out/blockouts"))
    ap.add_argument("--model-kind", default="Turbo", choices=["Turbo", "Base"],
                    help="Turbo=8-step fast, Base=50-step clean (default Turbo)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="actually fire ERNIE")
    g.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()

    raw = load_blockout(args.essence, args.animation_name)
    if raw is None:
        print(f"No corpus blockout found for {args.essence}/{args.animation_name}", file=sys.stderr)
        print(f"  Expected: scaffolds/.claude/blockouts/{args.essence}/{args.animation_name}.json", file=sys.stderr)
        return 1

    target_dir = args.out / args.essence / args.animation_name
    prompts = blockout_prompts(raw)
    seed_label = blockout_seed(raw)
    directions = raw["directions"]

    if not args.apply:
        print(f"DRY-RUN plan for {args.essence}/{args.animation_name}:")
        print(f"  target dir:   {target_dir}")
        print(f"  seed_label:   {seed_label}")
        print(f"  model_kind:   {args.model_kind}")
        print(f"  directions:   {directions}")
        print(f"  rotation_angles: {raw['rotation_angles']}")
        print(f"  anim_frame_targets: {raw.get('anim_frame_targets', {})}")
        print(f"  ERNIE calls: {len(directions)} (same seed={_seed_int(seed_label)} pinned across all)")
        print(f"\n  Per-direction prompts:")
        for d in directions:
            print(f"    [{d}] {prompts[d][:110]}...")
        print(f"\n  Post: assemble_from_corpus → {target_dir}/{args.essence}_{args.animation_name}_movement_blockout.png")
        print(f"\nRun with --apply to fire ERNIE + assemble.")
        return 0

    # Live fire
    target_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    direction_to_frame: dict[str, Path] = {}
    for d in directions:
        dest = target_dir / f"frame_{d}.png"
        if dest.exists():
            print(f"  [{d}] cached")
            direction_to_frame[d] = dest
            continue
        print(f"  [{d}] firing ERNIE ({args.model_kind})...")
        t_dir = time.time()
        _fire_ernie_direction(prompts[d], seed_label, dest, model_kind=args.model_kind)
        direction_to_frame[d] = dest
        print(f"    → {dest.name} ({time.time()-t_dir:.1f}s)")

    print(f"\nAssembling blockout via assemble_from_corpus...")
    result = assemble_from_corpus(
        essence=args.essence,
        animation_name=args.animation_name,
        direction_to_frame=direction_to_frame,
        out_dir=target_dir,
    )
    if result is None:
        print("ERROR: assemble_from_corpus returned None (spec lookup failed)", file=sys.stderr)
        return 1

    elapsed = time.time() - t0
    print(f"\n✅ done in {elapsed:.1f}s")
    print(f"   sheet:   {result['sheet']}")
    print(f"   manifest: {result['manifest']}")
    print(f"   spec:    {result['spec']}")
    print(f"   preview: {result['labeled']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
