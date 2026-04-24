"""Postprocess for parallax_backdrop workflow.

ERNIE returns 1024×1024 photo-mode output per layer call. This module:

  1. feather_edges_horizontal(img, feather_px)
       - alpha-feather left + right edges so horizontal-scroll tiling is
         seam-blended. Does NOT feather top/bottom (those are the image
         frame, not neighbors).
  2. stretch_to_target(img, target_w, target_h)
       - horizontal-axis stretch from ERNIE's square 1024² to the
         engine-target canvas (default 3200×224 for NES-era; 3200×448
         for SNES; 1024² for mode7_floor which stays square).
  3. assemble_3layer(far, mid, near, out_dir, seed_label)
       - takes 3 ERNIE outputs, seam-blends each, writes matching
         backdrop_<seed>_far.png / _mid.png / _near.png under out_dir.
  4. verify_tileable_horizontal(img, out_path)
       - paste the image 1×3 horizontally and save canary_wrap_*.png
         for eyeball validation. No automated seam metric.

Matches `tileable_terrain/postprocess.py` patterns where applicable
(shared seam-blend intent + canary-wrap verification).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def feather_edges_horizontal(img_path: Path, feather_px: int = 16) -> Image.Image:
    """Apply radial-cosine alpha feather to left + right edges for
    horizontal-tile seamless blending. Top + bottom stay opaque
    (they're the image frame, not neighbors)."""
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size
    if w < 2 * feather_px:
        raise ValueError(f"image ({w}px wide) too narrow for feather_px={feather_px}")
    arr = np.array(img)
    # Build an alpha ramp: full at center, cosine-ramp to 0 at edges.
    alpha = arr[:, :, 3].astype(np.float32) / 255.0
    ramp_l = 0.5 * (1 - np.cos(np.linspace(0, np.pi, feather_px)))  # 0 → 1
    ramp_r = ramp_l[::-1]
    alpha[:, :feather_px] *= ramp_l[np.newaxis, :]
    alpha[:, -feather_px:] *= ramp_r[np.newaxis, :]
    arr[:, :, 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def stretch_to_target(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize ERNIE's 1024² output to the engine-target canvas.
    For 3200×224 NES-era: 1024² → 3200 wide means ~3.1× horizontal
    stretch. Pixel-art aesthetic tolerates this; painted backdrops
    may need upscaling via a dedicated model for best results."""
    return img.resize((target_w, target_h), Image.LANCZOS)


def assemble_3layer(
    far_path: Path, mid_path: Path, near_path: Path,
    out_dir: Path, seed_label: str,
    target_w: int = 3200, target_h: int = 224,
    feather_px: int = 16,
) -> dict:
    """Process a 3-layer set from ERNIE outputs. Writes:
      <out_dir>/backdrop_<seed_label>_far.png
      <out_dir>/backdrop_<seed_label>_mid.png
      <out_dir>/backdrop_<seed_label>_near.png
    Returns a manifest dict with paths + layer params."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    layer_meta = [
        ("far",  far_path,  0.25),
        ("mid",  mid_path,  0.50),
        ("near", near_path, 0.75),
    ]
    for name, src, scroll in layer_meta:
        img = feather_edges_horizontal(src, feather_px=feather_px)
        img = stretch_to_target(img, target_w, target_h)
        dst = out_dir / f"backdrop_{seed_label}_{name}.png"
        img.save(dst)
        paths[name] = {"path": str(dst), "scroll_speed_ratio": scroll}
    manifest = {
        "seed_label": seed_label,
        "canvas": {"w": target_w, "h": target_h},
        "feather_px": feather_px,
        "layers": paths,
    }
    return manifest


def assemble_single(
    src_path: Path, out_dir: Path, seed_label: str,
    target_w: int = 3200, target_h: int = 224,
    feather_px: int = 16,
) -> dict:
    """Single-layer (NES-era) — one output PNG."""
    out_dir.mkdir(parents=True, exist_ok=True)
    img = feather_edges_horizontal(src_path, feather_px=feather_px)
    img = stretch_to_target(img, target_w, target_h)
    dst = out_dir / f"backdrop_{seed_label}_single.png"
    img.save(dst)
    return {
        "seed_label": seed_label,
        "canvas": {"w": target_w, "h": target_h},
        "feather_px": feather_px,
        "path": str(dst),
        "scroll_speed_ratio": 1.0,
    }


def assemble_mode7(
    horizon_path: Path, floor_path: Path,
    out_dir: Path, seed_label: str,
    horizon_w: int = 3200, horizon_h: int = 112,
    floor_side: int = 1024,
) -> dict:
    """Mode-7 — produces a horizon strip + a square tileable floor.
    Floor does NOT get edge-feather (it's tileable in both axes; runtime
    does rotation + perspective-warp, so true seamlessness matters).
    Horizon gets left/right feather for horizontal scroll."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Horizon: feather + stretch to wide strip
    horizon_img = feather_edges_horizontal(horizon_path, feather_px=16)
    horizon_img = stretch_to_target(horizon_img, horizon_w, horizon_h)
    horizon_dst = out_dir / f"backdrop_{seed_label}_mode7_horizon.png"
    horizon_img.save(horizon_dst)
    # Floor: center-sample a tileable patch from ERNIE's 1024² output
    floor_img = Image.open(floor_path).convert("RGBA")
    fw, fh = floor_img.size
    side = min(floor_side, fw, fh)
    x0 = (fw - side) // 2
    y0 = (fh - side) // 2
    floor_img = floor_img.crop((x0, y0, x0 + side, y0 + side))
    floor_dst = out_dir / f"backdrop_{seed_label}_mode7_floor.png"
    floor_img.save(floor_dst)
    return {
        "seed_label": seed_label,
        "horizon": {"path": str(horizon_dst), "w": horizon_w, "h": horizon_h},
        "floor": {"path": str(floor_dst), "side": side, "tileable": True},
    }


def verify_tileable_horizontal(img_path: Path, out_path: Path, repeats: int = 3) -> None:
    """Paste the image `repeats` times horizontally and save, for
    eyeball seam-verification. No automated metric."""
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size
    canvas = Image.new("RGBA", (w * repeats, h))
    for i in range(repeats):
        canvas.paste(img, (i * w, 0), img)
    canvas.save(out_path)
