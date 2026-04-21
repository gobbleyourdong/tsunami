"""End-to-end sprite-sheet pipeline: bake → extract → pixelize.

Takes an entity YAML (e.g. scaffolds/engine/asset_library/entities/tree.yaml)
and a target pixel grid size, runs the full pipeline:

  1. bake_sprite_sheet.py — state graph → 1024² frames on magenta bg
  2. extract_alpha_unmix.py — un-premultiply magenta → clean RGBA
  3. pixelize_sheet.py — RGBA frames → target sprite-grid size

Output layout (same as bake, plus _rgba.png siblings + pixelized companions):

  <out-dir>/
    states/
      healthy_still.png              ← magenta-bg canonical
      healthy_still_rgba.png         ← straight RGBA (un-premix)
      ...
    transitions/<from>__<to>/
      frame_NNN.png                  ← magenta-bg canonical
      frame_NNN_rgba.png             ← straight RGBA
    loops/<name>/
      frame_NNN.png
      frame_NNN_rgba.png
    sheet.png                        ← composed magenta sprite sheet
    sheet_<N>.png                    ← pixelized to target grid (default 128)
    metadata.json
    metadata_<N>.json

Usage:

  python scripts/asset/end_to_end.py \\
      --entity scaffolds/engine/asset_library/entities/tree.yaml \\
      --out-dir /tmp/tree_final \\
      --target-size 128 \\
      --server http://127.0.0.1:8094

Default `--target-size 128` matches the `multi_angles` LoRA's canonical
turnaround grid; override to 64 for smaller NES-era sprites or 256 for
more detail. `--filter lanczos` (default) gives smooth downsamples;
`--filter nearest` gives harsh retro pixel-art look.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("end_to_end")

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent


def _run(argv: list[str]) -> int:
    """Run a subprocess, streaming output. Returns exit code."""
    log.info(f"[run] {' '.join(argv)}")
    return subprocess.call(argv)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--entity", required=True, type=Path,
                   help="entity YAML (from scaffolds/.../entities/)")
    p.add_argument("--out-dir", required=True, type=Path,
                   help="bake output + pixelize target directory")
    p.add_argument("--target-size", type=int, default=128,
                   help="final sprite grid size in pixels (default 128)")
    p.add_argument("--filter", default="lanczos",
                   choices=["lanczos", "bicubic", "bilinear", "nearest"],
                   help="downsample filter for pixelize (default lanczos)")
    p.add_argument("--base-resolution", type=int, default=1024,
                   help="bake generation resolution (default 1024)")
    p.add_argument("--steps", type=int, default=8,
                   help="inference steps (default 8, paired with lightning LoRA)")
    p.add_argument("--cfg", type=float, default=1.0,
                   help="true_cfg_scale (default 1.0, paired with lightning)")
    p.add_argument("--negative-prompt", default=" ",
                   help="negative prompt (default ' ', engages CFG in Qwen pipe)")
    p.add_argument("--seed", type=int, default=42,
                   help="deterministic seed (default 42)")
    p.add_argument("--server", default="http://127.0.0.1:8094",
                   help="qwen_image_server base URL")
    p.add_argument("--skip-bake", action="store_true",
                   help="reuse existing bake output in --out-dir; run only "
                        "extract + pixelize steps")
    p.add_argument("--skip-pixelize", action="store_true",
                   help="run bake + extract but skip the pixelize terminal pass")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()

    if not args.entity.is_file():
        print(f"ERROR: entity YAML not found: {args.entity}", file=sys.stderr)
        return 2

    bake = _HERE / "bake_sprite_sheet.py"
    unmix = _HERE / "extract_alpha_unmix.py"
    pixelize = _HERE / "pixelize_sheet.py"

    if not args.skip_bake:
        rc = _run([
            sys.executable, str(bake),
            "--entity", str(args.entity),
            "--out-dir", str(args.out_dir),
            "--server", args.server,
            "--base-resolution", str(args.base_resolution),
            "--steps", str(args.steps),
            "--cfg", str(args.cfg),
            "--negative-prompt", args.negative_prompt,
            "--seed", str(args.seed),
        ])
        if rc != 0:
            log.error(f"bake failed (exit {rc})")
            return rc

    # Extract alpha on every frame in the bake output.
    rc = _run([
        sys.executable, str(unmix),
        "--bake", str(args.out_dir),
    ])
    if rc != 0:
        log.error(f"extract_alpha_unmix failed (exit {rc})")
        return rc

    if not args.skip_pixelize:
        rc = _run([
            sys.executable, str(pixelize),
            "--bake", str(args.out_dir),
            "--size", str(args.target_size),
            "--filter", args.filter,
        ])
        if rc != 0:
            log.error(f"pixelize_sheet failed (exit {rc})")
            return rc

    log.info(
        f"[end_to_end] complete: bake + extract"
        f"{' + pixelize' if not args.skip_pixelize else ''} → {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
