"""Canonical sprite pipeline: UNMIX → BPAD → 4-CONN NAVY ring.

Four primitives, composed in order:
  1. UNMIX — soft-alpha un-premultiplication strips magenta contamination
             from silhouette-boundary pixels; binarizes alpha at 0.5.
  2. BPAD  — MidFord pattern-point stratified downsample on RGB + alpha
             at the SAME stride positions (prevents RGB/alpha boundary
             mismatch that produces spurious black pixels).
  3. bottom-align — resize to fit cell preserving aspect, bottom-align
             so feet land on a consistent row across azimuths.
  4. 4-CONN NAVY ring — 1-px 4-connected dilation of the silhouette,
             painted NAVY (36, 27, 59). 4-conn has no L-corners (see
             memory: outline_doctrine.md).

The separate PIXEL EXTRACT pipeline (tsunami/tools/pixel_extract.py)
handles messier inputs via Lab-space bg detection + perceptual edge
profile cuts; this canonical UNMIX→BPAD→4CONN path is the default for
clean magenta-keyed bakes.

Usage:
  python scripts/asset/pixelize.py --input sprite.png --output sprite_32.png
  python scripts/asset/pixelize.py --input dir/ --output out/ --target 32
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

_BPAD_DIR = Path(__file__).resolve().parent.parent.parent / "tsunami" / "vendor" / "BPAD"
sys.path.insert(0, str(_BPAD_DIR))
import pattern_noise as pn

MAGENTA = np.array([1.0, 0.0, 1.0], dtype=np.float32)
ALPHA_SOFT_FLOOR = 0.1
ALPHA_BIN_THRESHOLD = 0.5
TARGET = 32
NAVY = np.array([36, 27, 59], dtype=np.uint8)


def unmix_magenta(rgb_u8: np.ndarray) -> np.ndarray:
    """RGB uint8 HxWx3 → RGBA uint8 HxWx4 with clean 1-bit alpha (0 or 255).

    Magenta = (1, 0, 1). Green channel is 0 in BG, so Pg > 0 implies foreground.
    min(Pr, Pb) bounds magenta's contribution. Soft-alpha = 1 - clip(min(Pr,Pb) - Pg).
    RGB unmix math removes the magenta tint proportional to (1-α). Final alpha
    is binarized at 0.5 to avoid translucent BG residue."""
    rgb = rgb_u8.astype(np.float32) / 255.0
    Pr, Pg, Pb = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    magenta_rb = np.minimum(Pr, Pb)
    alpha_soft = 1.0 - np.clip(magenta_rb - Pg, 0.0, 1.0)
    alpha_bin = (alpha_soft >= ALPHA_BIN_THRESHOLD).astype(np.float32)

    a_soft_safe = np.where(alpha_soft > ALPHA_SOFT_FLOOR, alpha_soft, 1.0)[..., None]
    F = (rgb - (1 - alpha_soft[..., None]) * MAGENTA) / a_soft_safe
    F = np.clip(F, 0.0, 1.0)
    F[alpha_bin == 0] = 0.0

    rgba = np.concatenate([F, alpha_bin[..., None]], axis=-1)
    return (rgba * 255.0 + 0.5).astype(np.uint8)


def bpad_rgba(rgba: np.ndarray, w: int, h: int) -> np.ndarray:
    """Joint RGB+alpha pattern-point downsample. One source pixel per output
    cell, sampled at stride-interval start so 1-2px features (eye highlights,
    mouth, outline breaks) survive instead of being majority-voted away."""
    H, W = rgba.shape[:2]
    xPat = pn.create_pattern(W, w)
    yPat = pn.create_pattern(H, h)

    xs, lastX = [], 0
    for i in range(w):
        xs.append(min(lastX if i != w - 1 else W - 1, W - 1))
        lastX += xPat[i]
    ys, lastY = [], 0
    for j in range(h):
        ys.append(min(lastY if j != h - 1 else H - 1, H - 1))
        lastY += yPat[j]

    out = np.zeros((h, w, rgba.shape[2]), dtype=rgba.dtype)
    for i, sx in enumerate(xs):
        for j, sy in enumerate(ys):
            out[j, i] = rgba[sy, sx]
    return out


def dilate_4conn(mask: np.ndarray) -> np.ndarray:
    """1-px 4-connected dilation (N/S/E/W, no diagonal L-corners).
    Ref: outline_doctrine.md — 8-conn produces L-shapes at convex silhouette
    corners which read as blobby; 4-conn alone gives the crisp diagonal
    outline seen in LTTP/SotN references."""
    out = mask.copy()
    out[1:]  |= mask[:-1]
    out[:-1] |= mask[1:]
    out[:, 1:]  |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def tight_crop_to_bbox(rgba: np.ndarray, margin: int = 4) -> np.ndarray:
    a = rgba[..., 3]
    opaque = np.argwhere(a > 0)
    if len(opaque) == 0:
        return rgba
    y0, x0 = opaque.min(axis=0)
    y1, x1 = opaque.max(axis=0) + 1
    y0, x0 = max(0, y0 - margin), max(0, x0 - margin)
    y1 = min(rgba.shape[0], y1 + margin)
    x1 = min(rgba.shape[1], x1 + margin)
    return rgba[y0:y1, x0:x1]


def pixelize(rgb_u8: np.ndarray, target: int = TARGET,
             outline_ring: bool = True) -> np.ndarray:
    """Magenta-keyed RGB (any size) → target×target RGBA with NAVY ring.

    UNMIX → tight-crop → fit-in-cell preserving aspect → BPAD joint
    RGB+α sample → bottom-align → optional 4-conn NAVY ring."""
    rgba = unmix_magenta(rgb_u8)
    rgba = tight_crop_to_bbox(rgba, margin=4)

    h, w = rgba.shape[:2]
    scale = min(target / w, target / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    small = bpad_rgba(rgba, new_w, new_h)
    rgb_small = small[..., :3].copy()
    a_small = small[..., 3]
    rgb_small[a_small == 0] = 0

    out = np.zeros((target, target, 4), dtype=np.uint8)
    x_off = (target - new_w) // 2
    y_off = target - new_h
    out[y_off:y_off+new_h, x_off:x_off+new_w, :3] = rgb_small
    out[y_off:y_off+new_h, x_off:x_off+new_w, 3]  = a_small

    if outline_ring:
        char = out[..., 3] > 0
        ring = dilate_4conn(char) & ~char
        out[ring, :3] = NAVY
        out[ring, 3]  = 255

    return out


def _process_file(src: Path, dst: Path, target: int, outline_ring: bool) -> None:
    rgb = np.asarray(Image.open(src).convert("RGB"))
    out = pixelize(rgb, target=target, outline_ring=outline_ring)
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, "RGBA").save(dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input",  required=True, help="PNG file or directory of PNGs")
    ap.add_argument("--output", required=True, help="output PNG path or directory")
    ap.add_argument("--target", type=int, default=TARGET, help="sprite cell size (default 32)")
    ap.add_argument("--no-outline", action="store_true", help="skip 4-conn NAVY ring")
    args = ap.parse_args()

    src = Path(args.input)
    dst = Path(args.output)
    outline = not args.no_outline

    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for png in sorted(src.glob("*.png")):
            _process_file(png, dst / png.name, args.target, outline)
            print(f"  {png.name} → {dst / png.name}")
    else:
        _process_file(src, dst, args.target, outline)
        print(f"  {src} → {dst}")


if __name__ == "__main__":
    main()
