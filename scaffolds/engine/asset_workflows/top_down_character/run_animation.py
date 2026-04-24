"""Post-blockout animation pass: per-direction Qwen chain-edits.

`run_blockout.py` produces ONE frame per direction (the canonical
mid-stride pose). For a walk cycle with `anim_frame_targets: {"walk": 2}`,
the second frame is a Qwen-Image-Edit nudge off the first — identity
preserved, pose alternated (other foot forward).

This script reads the `.spec.json` companion written by
`assemble_from_corpus` + the per-direction frame PNGs, then for each
anim in `anim_frame_targets` fires Qwen `/v1/images/animate` per
direction to produce frames 1..N-1.

Generic nudge per anim (no corpus-specific phasing yet — sister's
progression_descriptions don't typically split per-direction):

- walk:  "same character, opposite foot forward, slight torso counter-bob"
- run:   "same character, next stride phase, arms extended, legs spread"
- idle:  "same character, subtle breathing shift, shoulders slightly down"
- attack:"same character, weapon arc mid-swing, leading arm extended"
- hurt:  "same character, pose compressed, head tilted back slightly"
- death: "same character, pose falling forward, legs buckling"
- cast:  "same character, arms raised, magic energy gathering"

Usage (dry-run — no Qwen calls):
    python3 run_animation.py ./out/blockouts/1986_dragon_quest/hero_plainclothes_walk/

Live fire (requires Qwen-Image-Edit :8094):
    python3 run_animation.py ./out/blockouts/1986_dragon_quest/hero_plainclothes_walk/ --apply

Output per direction: frame_<D>_001.png, frame_<D>_002.png, ...
All cells per direction are assembled into a per-direction strip at end.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests  # type: ignore
except ImportError:
    requests = None

QWEN_EDIT_URL = os.environ.get("QWEN_EDIT_URL", "http://localhost:8094")

# Generic per-anim nudge templates. Scaffolds can override by editing
# the spec.json directly or patching this module. These describe the
# DELTA from the canonical mid-stride pose — Qwen chain-edits off frame 0.
NUDGE_TEMPLATES = {
    "walk": [
        "same character, opposite foot forward, slight torso counter-bob",
    ],
    "run": [
        "same character, next stride phase, arms extended, legs spread wider",
    ],
    "idle": [
        "same character, subtle breathing shift, shoulders slightly down",
        "same character, shoulders back to neutral, small weight shift to other foot",
        "same character, weight back, breathing cycle continuing",
    ],
    "attack_light": [
        "same character, windup — arms pulled back, weight on back foot",
        "same character, swing mid-arc, weapon extended",
        "same character, follow-through, weapon past target",
        "same character, recovery, returning to ready stance",
    ],
    "attack": [
        "same character, weapon arc mid-swing, leading arm extended",
        "same character, weapon past target, follow-through",
        "same character, recovery toward ready stance",
    ],
    "hurt": [
        "same character, pose compressed, head tilted back from impact",
        "same character, staggered backward, arms flailed",
    ],
    "death": [
        "same character, falling forward, legs buckling",
        "same character, collapsed on ground, limbs splayed",
    ],
    "cast": [
        "same character, arms raised, magic energy gathering at fingertips",
        "same character, energy peak, hands extended outward",
        "same character, release — energy projected forward",
        "same character, recovery, arms falling back to sides",
    ],
    "shoot": [
        "same character, bow drawn back or gun raised, aiming forward",
        "same character, projectile released, slight recoil",
        "same character, recovery to idle stance",
    ],
}


def _seed_int(label: str, salt: str = "") -> int:
    return int(hashlib.sha256((label + salt).encode()).hexdigest()[:8], 16)


def _fire_qwen_chain(
    base_path: Path, nudges: list[str], save_dir: Path, seed_label: str,
) -> list[Path]:
    """Fire Qwen /v1/images/animate, return ordered list of frame paths."""
    if requests is None:
        raise SystemExit("requests not installed")
    save_dir.mkdir(parents=True, exist_ok=True)
    body = {
        "path": str(base_path.absolute()),
        "nudges": [
            {"delta": n, "strength": 0.4, "num_inference_steps": 20, "guidance_scale": 4.0}
            for n in nudges
        ],
        "negative_prompt": "text, UI, 3D rendering, different character",
        "seed": _seed_int(seed_label, "_qwen"),
        "response_format": "save_path",
        "save_dir": str(save_dir.absolute()),
    }
    try:
        r = requests.post(f"{QWEN_EDIT_URL}/v1/images/animate", json=body, timeout=3600)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise SystemExit(
            f"Qwen-Image-Edit not reachable at {QWEN_EDIT_URL}. Bring it up first:\n"
            f"  python -m tsunami.serving.qwen_image_server --port 8094"
        )
    except requests.exceptions.HTTPError:
        raise SystemExit(f"Qwen returned {r.status_code}: {r.text[:200]}")
    result = r.json()
    paths = []
    for f in result.get("frames", []):
        p = Path(f["save_path"])
        if p.exists():
            paths.append(p)
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("blockout_dir", type=Path,
                    help="dir from run_blockout.py (contains frame_<D>.png + .spec.json)")
    ap.add_argument("--anim", default="walk",
                    help="which anim from anim_frame_targets to produce (default: walk)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="actually fire Qwen")
    g.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()

    if not args.blockout_dir.is_dir():
        print(f"ERROR: {args.blockout_dir} not a directory", file=sys.stderr)
        return 1

    # Find the .spec.json companion written by assemble_from_corpus
    spec_files = list(args.blockout_dir.glob("*_movement_blockout.spec.json"))
    if not spec_files:
        print(f"ERROR: no *_movement_blockout.spec.json in {args.blockout_dir}", file=sys.stderr)
        print(f"  (run run_blockout.py --apply first to produce the blockout)", file=sys.stderr)
        return 1
    spec = json.loads(spec_files[0].read_text())

    directions = spec.get("directions") or []
    anim_frame_targets = spec.get("anim_frame_targets") or {}
    target_frames = anim_frame_targets.get(args.anim)
    if not target_frames or target_frames < 2:
        print(f"Anim '{args.anim}' not in anim_frame_targets or < 2 frames required.")
        print(f"  Available: {anim_frame_targets}")
        return 1
    nudges_per_direction = NUDGE_TEMPLATES.get(args.anim, NUDGE_TEMPLATES["walk"])[:target_frames - 1]

    seed_label = args.blockout_dir.name  # assumes dir name matches animation_name
    print(f"Anim: {args.anim} · target_frames: {target_frames} · nudges: {len(nudges_per_direction)}")
    print(f"Directions: {directions}")
    print(f"Nudge templates:")
    for i, n in enumerate(nudges_per_direction):
        print(f"  [{i+1}] {n}")

    if not args.apply:
        print(f"\nDRY-RUN plan:")
        for d in directions:
            base = args.blockout_dir / f"frame_{d}.png"
            out_dir = args.blockout_dir / f"animated_{args.anim}" / d
            print(f"  [{d}] Qwen chain from {base.name} × {len(nudges_per_direction)} nudges → {out_dir.relative_to(args.blockout_dir)}/")
        print(f"\nRun with --apply to fire Qwen.")
        return 0

    # Live fire
    t0 = time.time()
    for d in directions:
        base = args.blockout_dir / f"frame_{d}.png"
        if not base.exists():
            print(f"  [{d}] SKIP — no base frame at {base}")
            continue
        out_dir = args.blockout_dir / f"animated_{args.anim}" / d
        print(f"\n  [{d}] firing Qwen chain off {base.name} ({len(nudges_per_direction)} nudges)...")
        t_dir = time.time()
        paths = _fire_qwen_chain(
            base_path=base, nudges=nudges_per_direction, save_dir=out_dir,
            seed_label=f"{seed_label}_{d}_{args.anim}",
        )
        print(f"    → {len(paths)} frames ({time.time()-t_dir:.1f}s)")

    print(f"\n✅ animation pass done in {time.time()-t0:.1f}s")
    print(f"   per-direction output: {args.blockout_dir}/animated_{args.anim}/<D>/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
