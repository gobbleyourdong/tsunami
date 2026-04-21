"""Un-premultiply a magenta-keyed bake sheet / frame dir into clean RGBA.

Terminal pass of the asset-graph pipeline for subject-category primitives:

  bake (magenta bg)  ──►  THIS TOOL  ──►  RGBA (straight FG color + α)

The bake renders every state/transition/loop frame on a magenta
(#FF00FF) background. Classical hard-chroma keying works for opaque
interior pixels but fails at edges / smoke / dust / glow — those
pixels are a BLEND of foreground and magenta bg, and a hard threshold
either keeps the pink fringe (magenta contaminating the FG color) or
discards the whole translucent region (losing dust/smoke entirely).

The fix is un-premultiplication: solve `P = α·F + (1-α)·M` for F and
α per pixel, assuming M = magenta. Then the observed pink dust particle
comes out as its straight color (grey/white/whatever the subject was)
with a partial alpha, so compositing it over a different background
gives correct results.

## Alpha estimation

Magenta is (1, 0, 1) normalized. Key observation: the green channel
of magenta is zero, so any observed Pg > 0 must come from the
foreground. And the R and B channels are at magenta's maximum — so
`min(Pr, Pb)` gives a lower bound on the magenta's contribution
(regardless of what additional R or B the subject added).

Per-pixel:
    magenta_rb  = min(Pr, Pb)        # ∈ [0, 1]
    subject_g   = Pg                 # magenta adds 0 here
    alpha       = 1 - clamp(magenta_rb - subject_g, 0, 1)

Check:
  - Pure magenta (1, 0, 1):   alpha = 1 - (1 - 0) = 0                ✓
  - Pure green  (0, 1, 0):   alpha = 1 - clamp(0 - 1, 0, 1) = 1     ✓
  - 50% blue subject mix:    P = (0.5, 0, 1) → α = 1 - 0.5 = 0.5    ✓
  - 70% grey subject mix:    P = (0.51, 0.21, 0.51) → α = 0.70      ✓

## Un-premultiplication

With α known and M = (1, 0, 1):
    F = (P - (1-α)·M) / α

Where the division by α amplifies numerical noise near transparent
regions, so we floor α by a small epsilon before dividing.

## Usage

  python scripts/asset/extract_alpha_unmix.py --bake /tmp/bake_crystal_v4_magenta
  python scripts/asset/extract_alpha_unmix.py --frame path/to/frame.png --out path/to/out.png
  python scripts/asset/extract_alpha_unmix.py --bake <dir> --update-sheet

--bake mode walks the directory, processing states/*.png and every
frame_NNN.png under transitions/ and loops/. RGBA outputs land next
to the inputs with a `_rgba.png` suffix (so the original magenta
frames stay on disk for debugging + re-extraction).

--update-sheet optionally rebuilds sheet.png from the new RGBA frames.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger("unmix")


MAGENTA = np.array([1.0, 0.0, 1.0], dtype=np.float32)
ALPHA_EPSILON = 1e-3  # below this α, unmix result is numerical noise


def unmix_magenta(rgb: np.ndarray) -> np.ndarray:
    """RGB uint8 HxWx3 → RGBA uint8 HxWx4 with magenta key un-premultiplied.

    Pure numpy, no GPU. Processes a 1024² frame in ~40 ms."""
    if rgb.ndim != 3 or rgb.shape[-1] not in (3, 4):
        raise ValueError(f"expected H×W×3 or H×W×4, got {rgb.shape}")
    if rgb.shape[-1] == 4:
        # Already RGBA; strip alpha (we're computing a new one) but keep the
        # shape info around for callers that want it.
        rgb = rgb[..., :3]
    arr = rgb.astype(np.float32) / 255.0
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]

    # Alpha: how much is this pixel FG vs magenta?
    magenta_rb = np.minimum(R, B)
    alpha = 1.0 - np.clip(magenta_rb - G, 0.0, 1.0)

    # Un-premultiply: F = (P - (1-α)·M) / α
    # M = (1, 0, 1); M_g = 0, so F_g = G / α
    safe_a = np.maximum(alpha, ALPHA_EPSILON)
    one_minus = 1.0 - alpha
    F_r = np.clip((R - one_minus * MAGENTA[0]) / safe_a, 0.0, 1.0)
    F_g = np.clip((G - one_minus * MAGENTA[1]) / safe_a, 0.0, 1.0)
    F_b = np.clip((B - one_minus * MAGENTA[2]) / safe_a, 0.0, 1.0)

    rgba = np.dstack([F_r, F_g, F_b, alpha]) * 255.0
    return rgba.astype(np.uint8)


def process_frame(src: Path, dst: Path) -> None:
    """Load src PNG, un-premultiply, write dst as RGBA PNG."""
    rgb = np.asarray(Image.open(src).convert("RGB"))
    rgba = unmix_magenta(rgb)
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(dst, format="PNG")
    # Quick stats for logging
    a = rgba[..., 3]
    solid = int((a > 250).sum())
    partial = int(((a > 10) & (a <= 250)).sum())
    empty = int((a <= 10).sum())
    log.info(
        f"[unmix] {src.name} → {dst.name}: "
        f"solid={solid} partial={partial} empty={empty}"
    )


def walk_bake_dir(bake_dir: Path) -> list[tuple[Path, Path]]:
    """Return (src, dst) pairs for every PNG in the bake dir.

    Skips anything already named *_rgba.png (our own output) and the
    __base_upscaled.png canonical source (it's the magenta-bg input,
    not a frame to extract)."""
    pairs: list[tuple[Path, Path]] = []
    patterns = [
        "states/*.png",
        "transitions/*/frame_*.png",
        "loops/*/frame_*.png",
    ]
    for pat in patterns:
        for src in sorted(bake_dir.glob(pat)):
            if src.name.endswith("_rgba.png"):
                continue
            if src.name.startswith("__"):
                continue
            dst = src.with_name(src.stem + "_rgba.png")
            pairs.append((src, dst))
    return pairs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--bake", type=Path,
                   help="bake output directory to walk end-to-end")
    g.add_argument("--frame", type=Path,
                   help="single frame PNG (requires --out)")
    p.add_argument("--out", type=Path, default=None,
                   help="output path for --frame mode (RGBA PNG)")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()

    if args.frame:
        if not args.frame.is_file():
            print(f"ERROR: frame not found: {args.frame}", file=sys.stderr)
            return 2
        if args.out is None:
            print("ERROR: --out required with --frame", file=sys.stderr)
            return 2
        process_frame(args.frame, args.out)
        return 0

    if not args.bake.is_dir():
        print(f"ERROR: bake dir not found: {args.bake}", file=sys.stderr)
        return 2

    pairs = walk_bake_dir(args.bake)
    if not pairs:
        print(f"ERROR: no frames found under {args.bake}", file=sys.stderr)
        return 2

    log.info(f"[unmix] {args.bake} — {len(pairs)} frames to process")
    for src, dst in pairs:
        process_frame(src, dst)
    log.info(f"[unmix] done — {len(pairs)} frames extracted to RGBA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
