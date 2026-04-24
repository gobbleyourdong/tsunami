"""One-command character pipeline: blockout → animation → strip.

Chains the three phases into a single runnable script so a DQ hero run
becomes one command instead of three. Idempotent — each phase checks
for existing outputs and skips if fresh.

Phases:
  1. blockout      (run_blockout): ERNIE × N directions, pinned seed
  2. animation     (run_animation): Qwen chain per direction (if anim
                   in anim_frame_targets)
  3. strip assembly (strip_assembler): each direction's frames → N×1 strip

Usage:
    # Dry-run: print plan, no server calls
    python3 make_character.py 1986_dragon_quest hero_plainclothes_walk

    # Live fire
    python3 make_character.py 1986_dragon_quest hero_plainclothes_walk --apply

    # Skip the animation phase (blockout only)
    python3 make_character.py 1986_dragon_quest hero_plainclothes_walk --apply --no-animation

    # Different anim (default walk)
    python3 make_character.py 1986_dragon_quest elder_wizard_walk --apply --anim idle
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent / "_common"))
sys.path.insert(0, str(_HERE))

from blockout_loader import load_blockout  # noqa: E402


def _run(cmd: list[str], cwd: Path) -> int:
    """Invoke a subcommand, stream its output, return exit code."""
    print(f"  $ {' '.join(str(x) for x in cmd)}")
    return subprocess.call(cmd, cwd=str(cwd))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("essence")
    ap.add_argument("animation_name")
    ap.add_argument("--out", type=Path, default=Path("./out/blockouts"))
    ap.add_argument("--model-kind", default="Turbo", choices=["Turbo", "Base"])
    ap.add_argument("--anim", default="walk",
                    help="anim from anim_frame_targets for phase 2 (default walk)")
    ap.add_argument("--no-animation", action="store_true",
                    help="skip phase 2 (Qwen chain)")
    ap.add_argument("--no-strip", action="store_true",
                    help="skip phase 3 (strip assembly)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()

    # Pre-flight: load the corpus spec
    raw = load_blockout(args.essence, args.animation_name)
    if raw is None:
        print(f"ERROR: no corpus spec for {args.essence}/{args.animation_name}", file=sys.stderr)
        return 1

    target_dir = args.out / args.essence / args.animation_name
    anim_available = raw.get("anim_frame_targets", {}).get(args.anim)
    will_animate = bool(anim_available) and not args.no_animation

    print(f"=== make_character: {args.essence}/{args.animation_name} ===")
    print(f"  directions: {raw['directions']}")
    print(f"  anim_frame_targets: {raw.get('anim_frame_targets', {})}")
    print(f"  target_dir: {target_dir}")
    print(f"  will run phase 2 ({args.anim})?  {will_animate}")
    print(f"  will run phase 3 (strip)?        {not args.no_strip}")

    if not args.apply:
        print(f"\nDRY-RUN. Would execute in sequence:")
        print(f"  1. run_blockout.py --apply --model-kind {args.model_kind}")
        if will_animate:
            print(f"  2. run_animation.py {target_dir} --apply --anim {args.anim}")
        else:
            print(f"  2. (skipped)")
        if not args.no_strip:
            print(f"  3. strip_assembler.py {target_dir} (per-direction strips)")
        print(f"\nRun with --apply to execute.")
        return 0

    t0 = time.time()

    # Phase 1
    print(f"\n[phase 1] blockout")
    rc = _run([
        "python3", "run_blockout.py",
        args.essence, args.animation_name,
        "--apply", "--model-kind", args.model_kind,
        "--out", str(args.out),
    ], cwd=_HERE)
    if rc != 0:
        print(f"phase 1 failed ({rc}); stopping", file=sys.stderr)
        return rc

    # Phase 2
    if will_animate:
        print(f"\n[phase 2] animation ({args.anim})")
        rc = _run([
            "python3", "run_animation.py",
            str(target_dir.absolute()),
            "--apply", "--anim", args.anim,
        ], cwd=_HERE)
        if rc != 0:
            print(f"phase 2 failed ({rc}); stopping", file=sys.stderr)
            return rc
    else:
        print(f"\n[phase 2] animation — skipped")

    # Phase 3
    if not args.no_strip:
        print(f"\n[phase 3] strip assembly")
        # Assemble per-direction strips. For the blockout dir itself
        # (directional frames), we already have a blockout sheet from
        # phase 1's assemble_from_corpus. The animated output
        # (./out/blockouts/<essence>/<anim>/animated_<anim>/<D>/) has
        # per-direction frame_*.png from Qwen — one strip per direction.
        if will_animate:
            animated_root = target_dir / f"animated_{args.anim}"
            if animated_root.is_dir():
                rc = _run([
                    "python3", str(_HERE.parent / "_common" / "strip_assembler.py"),
                    str(animated_root.absolute()),
                    "--recurse",
                ], cwd=_HERE)
                if rc != 0:
                    print(f"phase 3 failed ({rc}); stopping", file=sys.stderr)
                    return rc
            else:
                print(f"  animated_{args.anim} dir not found — skipping per-direction strips")
        else:
            print(f"  no animation phase — only blockout sheet exists (already assembled)")
    else:
        print(f"\n[phase 3] strip — skipped")

    print(f"\n✅ make_character done in {time.time()-t0:.0f}s")
    print(f"   outputs under: {target_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
