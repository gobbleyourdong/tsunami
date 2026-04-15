"""Composable image post-processing primitives.

Two stand-alone tools that consume a PIL image and emit a PIL image:

  pixelize(img, pixel_rows, palette)        block-downsample to a chunky
                                            grid + palette-quantize. Keeps
                                            the entire scene incl. background
                                            (use this for banners, scenes).

  extract_bg(img, bg_color, tolerance)      alpha-key the background out
                                            (foreground stays opaque, bg
                                            becomes transparent). Uses
                                            pixel_extract.extract_alpha for
                                            iterative two-threshold fringe
                                            peel and small-island cleanup.

Compose them: gen → extract_bg → pixelize for chunky transparent sprites,
gen → pixelize for full-scene retro banners, gen → extract_bg for clean
transparent logos.

─── PIXEL-ART CANONICAL SIZES ──────────────────────────────────────────

Industry-standard base resolutions (always 16:9 unless noted). When using
`pixelize`, set `pixel_rows` to the height row of these targets — `cols`
auto-derives from source aspect. For a banner generated at 1376×768 the
column count for each row target sits within ~1% of the canonical width.

  pixel_rows  base res     scale to 1080p   typical games
  ----------  -----------  ---------------  --------------------------
       180   320 × 180    6×               Celeste — classic 8-bit feel
       216   384 × 216    5×               middle-ground for detail
       270   480 × 270    4×               Hyper Light Drifter
       360   640 × 360    3×               Dead Cells, Owlboy — modern
       224   256 × 224    N/A              traditional NES/SNES (4:3)
       240   320 × 240    N/A              QVGA / 8-16-bit (4:3)

─── SPRITE/TILE GRID SIZES (use SQUARE source — gen at 1024×1024) ──────

When generating individual characters or tiles (square source), the
`pixel_rows` value IS the sprite size (since cols == rows on square input).
Stay consistent within a project so assets feel like they belong to the
same world.

  pixel_rows  sprite class           use case
  ----------  ---------------------  ----------------------------------
        16   Celeste-tier            very small, highly stylized chars
        32   the everyday standard   detailed-but-manageable characters
        64   HD boss / hero          large set-pieces, fighting-game tier

  Tiles (environment): 16×16 or 32×32 — the dominant industry norm.

The `sprite` workflow defaults to `pixel_rows=64` and the `icon` workflow
defaults to `pixel_rows=32`, both targeted at SQUARE-source generation.
For non-square source, output will be `pixel_rows × round(rows * W/H)`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image


# ─── pixelize ──────────────────────────────────────────────────────────

def pixelize(
    img: Image.Image,
    pixel_rows: int = 270,
    palette: int = 32,
    upscale: int = 4,
) -> Image.Image:
    """Block-downsample the entire image to a chunky `pixel_rows × cols`
    grid, then palette-quantize to `palette` colors.

    Preserves background — if you want the bg gone, run `extract_bg` FIRST.

    `pixel_rows`  vertical resolution of the logical pixel grid (cols
                  derived from aspect). See module docstring for the table
                  of canonical sizes:
                    180 → Celeste (chunky 8-bit)
                    216 → middle-ground
                    270 → Hyper Light Drifter (default — sharp + readable)
                    360 → Dead Cells / modern (barely pixelated)
                  For SQUARE square sprites (gen at 1024²): rows IS the
                  sprite size → 16 / 32 / 64.
    `palette`     number of distinct colors after quantization. 16 ≈ NES,
                  24-32 ≈ Genesis/SNES, 48-64 ≈ modern indie.
    `upscale`     if >1, nearest-neighbor upscale the result so each
                  logical pixel is `upscale × upscale` in the saved file.
                  Match to the canonical scale for clean integer scaling
                  (180p×6 = 1080p, 270p×4 = 1080p, 360p×3 = 1080p).
    """
    has_alpha = img.mode in ("RGBA", "LA")
    mode_pre = "RGBA" if has_alpha else "RGB"
    src = img.convert(mode_pre)
    W, H = src.size
    rows = max(1, int(pixel_rows))
    cols = max(1, round(rows * W / H))

    # BOX = mean of pixels in each block — the truest "snap to grid" downsample
    small = src.resize((cols, rows), Image.BOX)

    # Palette-quantize for the retro look. Quantization in 'P' mode handles
    # RGB only; for RGBA we strip alpha, quantize, then reattach.
    if has_alpha:
        rgb = small.convert("RGB")
        quant = rgb.convert("P", palette=Image.ADAPTIVE, colors=palette).convert("RGB")
        a = small.split()[-1]
        out = Image.merge("RGBA", (*quant.split(), a))
    else:
        out = small.convert("P", palette=Image.ADAPTIVE, colors=palette).convert("RGB")

    if upscale and upscale > 1:
        out = out.resize((cols * upscale, rows * upscale), Image.NEAREST)
    return out


# ─── extract_bg ─────────────────────────────────────────────────────────

@dataclass
class BgExtractConfig:
    """Knobs for background extraction. Friendly names mapped to
    `pixel_extract.ExtractConfig` (which has tighter, more legacy names).
    Defaults are tuned for AI-generated cartoon subjects on solid bg."""
    bg_match: float = 10.0          # ΔE: below this counts as definitely-bg (tight)
    fringe_threshold: float = 50.0  # ΔE: adjacent-to-transparent fringe peel (loose)
    palette_colors: int = 64        # palette size during analysis (not output)
    keep_largest_only: bool = True  # drop disconnected blobs (turn off to keep multi-subject)
    island_size: int = 5            # px area below which floating islands are pruned
    alpha_erosion_px: int = 1       # erode the mask edge by N source pixels (kills AA fringe)
    detect_edge_fraction: float = 0.5  # min border-cluster fraction to accept as bg


def extract_bg(
    img: Image.Image,
    cfg: Optional[BgExtractConfig] = None,
) -> Image.Image:
    """Strip the background, return RGBA with bg pixels as alpha=0.

    Wraps `tsunami.tools.pixel_extract.extract_alpha` — auto-detects the bg
    color from edge pixels, iteratively peels fringe pixels that are
    near-bg, cleans tiny islands. Output is RGBA at full input resolution.
    """
    from tsunami.tools.pixel_extract import extract_alpha, ExtractConfig

    cfg = cfg or BgExtractConfig()
    pe_cfg = ExtractConfig(
        bg_match_threshold=cfg.bg_match,
        border_fringe_threshold=cfg.fringe_threshold,
        max_palette_colors=cfg.palette_colors,
        keep_largest_only=cfg.keep_largest_only,
        island_size=cfg.island_size,
        alpha_erosion_px=cfg.alpha_erosion_px,
        detect_edge_fraction=cfg.detect_edge_fraction,
    )
    arr = np.asarray(img.convert("RGBA"))
    rgba = extract_alpha(arr, pe_cfg)
    return Image.fromarray(rgba, mode="RGBA")


# ─── workflow registry ─────────────────────────────────────────────────

# Small helper: compose stages on a PIL image, return the final PIL image
# plus a dict of per-stage timings.
def run_workflow(img: Image.Image, kind: str, **overrides) -> tuple[Image.Image, dict]:
    """Apply a named workflow to a generated image.

    Workflows:
      scene    — pass-through (no post-processing)
      pixelize — gen → pixelize @ 270 rows, 32 colors, 4× upscale (270p pixel-art look)
      logo     — extract_bg only (transparent PNG, keep_largest_only=False so wordmarks survive)
      icon     — extract_bg only (transparent PNG, keep_largest_only=True single-subject)
      sprite   — extract_bg + pixelize @ 64 rows, 16 colors, 8× upscale (only workflow combining both)

    `overrides` lets callers tune any pipeline knob:
      pixel_rows, palette, upscale, bg_color, fringe_tolerance,
      keep_largest_only, cleanup_min_size
    """
    import time

    timings = {}

    # Defaults per workflow — override-friendly. Post-processing knobs only;
    # model_kind / steps / cfg are gated server-side in WORKFLOW_GEN_DEFAULTS.
    # Canonical-size table is in the module docstring at the top.
    presets = {
        "scene":       {},
        # pixelize: 270p (Hyper-Light-Drifter base, 480×270, 4× scale to 1080p).
        # Sweet spot for text legibility + obvious pixel-art feel.
        "pixelize":    {"pixel_rows": 270, "palette": 32, "upscale": 4},
        "logo":        {"keep_largest_only": False},
        # sprite: 64×64 — HD-tier sprite. Use SQUARE source (gen at 1024²).
        # 8× upscale → 512×512 final. Drop to pixel_rows=32 for standard sprite.
        "sprite":      {"pixel_rows": 64, "palette": 16, "upscale": 8,
                        "keep_largest_only": True},
        # icon: gen + extract_bg only (no pixelize). Single-subject so
        # keep_largest_only=True peels any stray generator fringe regions.
        "icon":        {"keep_largest_only": True},
        # infographic: no post-processing; quality comes from Base DiT + 50 steps
        "infographic": {},
    }
    if kind not in presets:
        raise ValueError(f"unknown workflow {kind!r}; pick one of {list(presets)}")

    params = {**presets[kind], **overrides}
    needs_bg = kind in ("logo", "icon", "sprite") or "bg_color" in overrides
    needs_px = kind in ("pixelize", "sprite")

    out = img
    if needs_bg:
        t = time.time()
        bg_cfg = BgExtractConfig(
            bg_match=params.get("bg_match", 10.0),
            fringe_threshold=params.get("fringe_threshold", 50.0),
            palette_colors=params.get("bg_palette_colors", 64),
            keep_largest_only=params.get("keep_largest_only", True),
            island_size=params.get("island_size", 5),
            alpha_erosion_px=params.get("alpha_erosion_px", 1),
            detect_edge_fraction=params.get("detect_edge_fraction", 0.5),
        )
        out = extract_bg(out, bg_cfg)
        timings["extract_bg_s"] = round(time.time() - t, 3)

    if needs_px:
        t = time.time()
        out = pixelize(
            out,
            pixel_rows=params.get("pixel_rows", 120),
            palette=params.get("palette", 32),
            upscale=params.get("upscale", 1),
        )
        timings["pixelize_s"] = round(time.time() - t, 3)

    return out, timings
