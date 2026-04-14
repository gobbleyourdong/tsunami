"""
Pixel-art extractor for AI-generated sprites.

AI image models can't draw on a real pixel grid. Their "pixels" drift in size,
position, and color, and color-keying the background in RGB always leaves a
fringe — pixels that are tinted by the background but pass a hard distance
threshold, so they survive as opaque near-bg-colored pixels around the sprite.

This module solves both problems together in CIE Lab space:

  1. Detect or accept a transparency color and convert to Lab.
  2. Quantize the image to a palette that *includes* the transparency color,
     so any pixel whose nearest palette entry is bg becomes exactly bg.
  3. Recover the native pixel grid by analyzing perceptual-color edge profiles,
     fitting a spacing with L-BFGS-B, and placing cut-lines by peak prominence.
  4. Sample each cell at its center (nearest-neighbor) — not by mode vote,
     which can pick up edge-fringe pixels.
  5. Alpha with two thresholds: exact-bg, OR adjacent-to-bg-and-within-loose.
     The loose threshold only applies where fringe can physically exist — the
     1-pixel ring touching transparency — so it never eats into the interior.
  6. Optional small-island cleanup and symmetry centering.

Inspired by the approaches in Donitzo/ai-pixelart-extractor (MIT) and
Hugo-Dz/spritefusion-pixel-snapper (MIT). Reimplemented from scratch.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import minimize_scalar
from scipy.signal import find_peaks, peak_prominences
from skimage.color import deltaE_cie76, lab2rgb, rgb2gray, rgb2lab
from skimage.morphology import binary_dilation, disk, remove_small_objects


# ── Public API ────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExtractConfig:
    """Tunables for pixel-art extraction. Defaults match AI-gen sprites at 512px."""
    transparency_color_hex: str = "ff00ff"
    detect_transparency: bool = True
    detect_edge_fraction: float = 0.5       # min edge-cluster fraction to accept
    detect_cluster_radius: float = 45.0     # ΔE within which edge pixels merge
    # (AI bg colors drift internally by ΔE 20-40 — especially on gradient-ish
    # sky bgs where the top is a different shade than the bottom. Too tight
    # a radius fragments "should be one bg color" into several small clusters
    # and none cross the acceptance fraction. 45 merges most AI-drawn bg
    # gradient variants into one cluster without being so wide that it
    # accidentally pulls in subject colors.)
    # Three ΔE thresholds control bg/fringe/palette behavior independently.
    # bg_match is TIGHT — only ΔE<10 pixels count as definitely-bg. Widening
    # this eats light-colored subjects on light backgrounds (silver blade
    # on pink bg is ~ΔE 20, and a wider bg_match snaps it to transparent).
    # border_fringe is adjacency-gated and runs iteratively (see _make_alpha),
    # so multi-ring fringe peels away even at a moderate 25 ΔE threshold.
    # palette_merge is tight so sprite colors don't get collapsed together.
    bg_match_threshold: float = 10.0        # ΔE below this → counts as bg
    border_fringe_threshold: float = 50.0   # loose ΔE, adjacent-to-transparent only
    palette_merge_threshold: float = 10.0   # two palette entries merge below this
    max_palette_colors: int = 128
    max_pixel_size: int = 32                # largest native AI-pixel to consider
    min_peak_fraction: float = 0.2
    min_sprite_size: int = 4
    split_distance: Optional[int] = None    # if set, separate disconnected sprites
    land_dilution: int = 1
    island_size: int = 5
    symmetry_threshold: float = 0.5
    wavelet_denoise: bool = False  # blurs subject edges into bg — off by default
    keep_largest_only: bool = True  # islands-style: keep only the biggest
    # connected opaque blob, discard any smaller remnants (gradient stripes,
    # scene fragments the color-key couldn't fully remove)
    alpha_erosion_px: int = 1  # pre-pixelize erosion at FULL resolution.
    # Removes the outermost AA ring (1 source pixel) where the AI blended
    # subject color with bg color. Cheap and harmless — it shrinks the
    # silhouette by 1 source pixel, which after downsampling is sub-cell.
    min_peaks_required: int = 5             # fewer peaks than this → bail
    profile_smooth_sigma: float = 1.5       # gaussian on gradient profile; 0 disables
    coarser_grid_bias: float = 0.0          # prefer larger spacings within this fraction


@dataclass
class ExtractedSprite:
    rgba: np.ndarray                # uint8 (H, W, 4)
    pixel_size_x: float
    pixel_size_y: float
    centered_x: bool
    centered_y: bool


def extract(image: np.ndarray, config: ExtractConfig = ExtractConfig()) -> list[ExtractedSprite]:
    """Extract one or more sprites from an RGB(A) array (uint8 or float01)."""
    rgba = _as_float01_rgba(image)
    bg_rgb = _hex_to_rgb01(config.transparency_color_hex)
    rgb = _flatten_alpha(rgba, bg_rgb)

    if config.wavelet_denoise:
        rgb = _maybe_denoise(rgb)

    image_lab = rgb2lab(rgb)
    bg_lab = rgb2lab(bg_rgb.reshape(1, 1, 3)).reshape(3).astype(np.float32)

    if config.detect_transparency:
        detected, frac = _detect_edge_color(image_lab, config.detect_cluster_radius)
        if detected is not None and frac >= config.detect_edge_fraction:
            bg_lab = detected.astype(np.float32)

    subregions = (
        [image_lab]
        if config.split_distance is None
        else _split_subregions(image_lab, bg_lab, config.bg_match_threshold, config.split_distance)
    )

    sprites = []
    for region in subregions:
        sprite = _extract_one(region, bg_lab, config)
        if sprite is not None:
            sprites.append(sprite)
    return sprites


def extract_one(image: np.ndarray, config: ExtractConfig = ExtractConfig()) -> Optional[ExtractedSprite]:
    """Single-sprite convenience wrapper — returns the first result, or None."""
    results = extract(image, config)
    return results[0] if results else None


def snap(img: Image.Image, **overrides) -> Image.Image:
    """PIL-in, PIL-out convenience for one-shot use in existing pipelines."""
    arr = np.asarray(img.convert("RGBA"))
    config = ExtractConfig(**overrides) if overrides else ExtractConfig()
    result = extract_one(arr, config)
    if result is None:
        return img.copy()
    return Image.fromarray(result.rgba, mode="RGBA")


def pixelize(
    image: np.ndarray,
    pixel_rows: int = 32,
    palette_colors: int = 24,
    config: ExtractConfig = ExtractConfig(),
) -> np.ndarray:
    """Force a source image onto a uniform pixel grid — use when the generator
    produced a cartoon or illustration that wasn't pixel art, and you want to
    mechanically pixelize it rather than hoping grid recovery finds structure
    that isn't there.

    Alpha-first pipeline:
      1. `extract_alpha()` produces a clean RGBA at full source resolution —
         bg detection, palette quantize, iterative two-threshold fringe peel,
         small-island cleanup. All edge work happens at full res so subpixel
         fringe rings get cleaned before any resolution is lost.
      2. Mode-resample the full-res RGBA onto `pixel_rows × cols` blocks,
         where cols = round(pixel_rows * W / H). Each output pixel is the
         most-common RGBA 4-tuple in its block — transparency competes
         directly with opaque colors, so alpha edges stay crisp.

    Earlier ordering (downsample-then-alpha) had to decide transparency from
    a single center-sampled pixel per cell, letting tinted-bg pixels near
    subject edges survive as opaque fringe blocks. Alpha-first eliminates
    that because the fringe is already peeled away before blocks are cut.

    `pixel_rows` sets target vertical resolution; cols derive from aspect.
    `palette_colors` overrides `config.max_palette_colors` — typical pixel
    art uses 16-32 colors vs the default 128 used for full-res icons."""
    from dataclasses import replace

    # Only one knob differs between full-res alpha and pixelize: the palette
    # size. Override it in the config rather than forking extract_alpha's
    # logic — single source of truth for bg detection + fringe peel + alpha.
    cfg = replace(config, max_palette_colors=palette_colors) \
        if palette_colors != config.max_palette_colors else config

    rgba_full = extract_alpha(image, cfg)
    H, W = rgba_full.shape[:2]
    rows = max(1, int(pixel_rows))
    cols = max(1, round(rows * W / H))
    return _mode_downsample_rgba(rgba_full, rows, cols)


def _mode_downsample_rgba(rgba_u8: np.ndarray, rows: int, cols: int) -> np.ndarray:
    """Block-partition a uint8 RGBA image and emit one pixel per block whose
    value is the mode (most-common) RGBA 4-tuple in that block. Treating RGBA
    as a single packed token means transparency competes with every opaque
    color on equal footing — cells that are majority-transparent stay
    transparent, cells that are majority-opaque take the dominant opaque
    color (dithering and outline pixels preserved because they're discrete
    tokens, not averaged away)."""
    H, W = rgba_u8.shape[:2]
    edges_y = np.linspace(0, H, rows + 1).astype(int)
    edges_x = np.linspace(0, W, cols + 1).astype(int)
    out = np.zeros((rows, cols, 4), dtype=np.uint8)

    for yi in range(rows):
        ys, ye = edges_y[yi], edges_y[yi + 1]
        if ye <= ys:
            continue
        for xi in range(cols):
            xs, xe = edges_x[xi], edges_x[xi + 1]
            if xe <= xs:
                continue
            cell = rgba_u8[ys:ye, xs:xe]
            # Pack R<<24 | G<<16 | B<<8 | A into uint32 so the mode operation
            # treats each RGBA pixel as one unit (not per-channel averaging).
            packed = (
                (cell[:, :, 0].astype(np.uint32) << 24)
                | (cell[:, :, 1].astype(np.uint32) << 16)
                | (cell[:, :, 2].astype(np.uint32) << 8)
                | cell[:, :, 3].astype(np.uint32)
            ).ravel()
            unique, counts = np.unique(packed, return_counts=True)
            order = np.lexsort((unique, -counts))  # count desc, packed asc
            w = int(unique[order[0]])
            out[yi, xi] = [
                (w >> 24) & 0xFF,
                (w >> 16) & 0xFF,
                (w >> 8) & 0xFF,
                w & 0xFF,
            ]
    return out


def extract_alpha(image: np.ndarray, config: ExtractConfig = ExtractConfig()) -> np.ndarray:
    """Remove the background from any icon/logo/illustration at its original
    resolution — no grid recovery, no pixelation, no resampling.

    Runs the same Lab-space machinery as the pixel-art path (auto-detect bg,
    k-means palette with bg forced in, two-threshold edge-adjacent fringe
    peel), so near-bg fringe pixels get snapped to the bg class and become
    transparent by construction. Color-based keying means interior holes
    (letter A, donuts, gear teeth) are removed too — any pixel similar to
    bg becomes transparent regardless of spatial connectedness to the border.

    Returns uint8 RGBA at the input image's resolution."""
    rgba = _as_float01_rgba(image)
    bg_rgb = _hex_to_rgb01(config.transparency_color_hex)
    rgb = _flatten_alpha(rgba, bg_rgb)

    if config.wavelet_denoise:
        rgb = _maybe_denoise(rgb)

    image_lab = rgb2lab(rgb)
    bg_lab = rgb2lab(bg_rgb.reshape(1, 1, 3)).reshape(3).astype(np.float32)

    if config.detect_transparency:
        detected, frac = _detect_edge_color(image_lab, config.detect_cluster_radius)
        if detected is not None and frac >= config.detect_edge_fraction:
            bg_lab = detected.astype(np.float32)

    # Dynamic bg-match radius based on bg chroma. Highly-saturated bg colors
    # like magenta/lime/cyan sit in corners of Lab space where no legitimate
    # subject colors live — safe to use a wide snap radius (~30 ΔE) so all
    # the AI's internal magenta variants (which drift ΔE 15-30) get caught.
    # Low-chroma bg colors like gray/white/black sit near the L* axis, where
    # real subject colors (silver, light tan, pale pastels) DO live — they
    # need a tight radius (~10) so we don't eat subjects.
    bg_chroma = float(np.sqrt(bg_lab[1] ** 2 + bg_lab[2] ** 2))
    if bg_chroma >= 60.0:
        # Saturated bg (magenta/cyan/lime) — no legit subject colors live in
        # these Lab corners, and AI generators paint such bgs with heavy
        # internal variation (gradient "sky" → "ground" of the same hue can
        # span ΔE 40-50). Use a wide snap so every shade of the bg hue
        # collapses to transparent.
        bg_match = max(config.bg_match_threshold, 50.0)
    else:
        bg_match = config.bg_match_threshold

    _, apply_palette = _build_palette_quantizer(
        image_lab,
        bg_lab,
        config.max_palette_colors,
        bg_match,
        config.palette_merge_threshold,
    )
    indexed = apply_palette(image_lab)

    # Pass BOTH the palette-snapped image (for the strict "is exact bg?"
    # check) AND the original Lab values (for the loose adjacency-gated
    # check). Without the original values, the loose check misses dark-gray
    # AA edge pixels: they get mapped to a "dark blue" palette entry that's
    # > border_fringe ΔE from bg, so the snapped delta hides their true
    # near-bg origin. Checking against the original Lab catches them.
    rgb_out, alpha = _make_alpha(
        indexed, bg_lab, bg_match, config.border_fringe_threshold,
        loose_check_lab=image_lab,
    )
    rgba_out = np.dstack([rgb_out, alpha.astype(np.float32)])
    rgba_out = _cleanup_small_islands(rgba_out, config.land_dilution, config.island_size)
    if config.keep_largest_only:
        rgba_out = _keep_largest_region(rgba_out)
    if config.alpha_erosion_px > 0:
        rgba_out = _erode_alpha(rgba_out, config.alpha_erosion_px)
    return np.rint(np.clip(rgba_out, 0.0, 1.0) * 255.0).astype(np.uint8)


# ── Input conditioning ────────────────────────────────────────────

def _as_float01_rgba(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.dtype == np.uint8:
        arr = arr.astype(np.float32) / 255.0
    else:
        arr = arr.astype(np.float32)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[-1] == 3:
        alpha = np.ones(arr.shape[:2] + (1,), dtype=np.float32)
        arr = np.concatenate([arr, alpha], axis=-1)
    return arr


def _hex_to_rgb01(hex_str: str) -> np.ndarray:
    s = hex_str.lstrip("#")
    return np.array(
        [int(s[i : i + 2], 16) / 255.0 for i in (0, 2, 4)],
        dtype=np.float32,
    )


def _flatten_alpha(rgba: np.ndarray, bg_rgb: np.ndarray, alpha_cutoff: float = 0.5) -> np.ndarray:
    """Replace transparent pixels with the bg color so downstream ops work in RGB."""
    rgb = rgba[..., :3].copy()
    if rgba.shape[-1] == 4:
        rgb[rgba[..., 3] <= alpha_cutoff] = bg_rgb
    return rgb


_WARNED_MISSING_PYWT = False


def _maybe_denoise(rgb: np.ndarray) -> np.ndarray:
    """Denoise before Lab conversion. This step is load-bearing — without it,
    sub-pixel color drift inside what should be solid color blocks anchors its
    own k-means cluster centroids during palette construction. Fringe pixels
    then map to a dedicated "fringe" palette entry instead of being forced to
    the transparency color, and survive the alpha pass as visible magenta
    artifacts around the sprite.

    Wavelet denoising (via PyWavelets) is what actually works. The scipy
    Gaussian fallback is present only so the module imports without pywt; it
    is too weak to collapse the sub-pixel drift on AI-generated input."""
    try:
        from skimage.restoration import denoise_wavelet

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return denoise_wavelet(rgb, convert2ycbcr=True, rescale_sigma=True, channel_axis=2)
    except Exception:
        global _WARNED_MISSING_PYWT
        if not _WARNED_MISSING_PYWT:
            warnings.warn(
                "pixel_extract: PyWavelets not available; falling back to a weak "
                "Gaussian denoise. Expect fringe/artifact pixels in output. "
                "Install PyWavelets to fix (pip install PyWavelets).",
                RuntimeWarning,
                stacklevel=2,
            )
            _WARNED_MISSING_PYWT = True
        from scipy.ndimage import gaussian_filter

        return gaussian_filter(rgb, sigma=(0.8, 0.8, 0))


# ── Background detection ──────────────────────────────────────────

def _detect_edge_color(
    image_lab: np.ndarray,
    same_threshold: float,
    depth_ratio: float = 0.02,
) -> tuple[Optional[np.ndarray], float]:
    """Greedy cluster on edge pixels in Lab. Returns (mean_color, edge_fraction).
    Picks the largest perceptually-similar cluster along the image border."""
    depth = max(int(image_lab.shape[0] * depth_ratio) + 1, 1)
    edges = np.concatenate(
        [
            image_lab[:depth, :, :].reshape(-1, 3),
            image_lab[-depth:, :, :].reshape(-1, 3),
            image_lab[:, :depth, :].reshape(-1, 3),
            image_lab[:, -depth:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    if len(edges) == 0:
        return None, 0.0

    total = float(len(edges))
    best_color, best_frac = None, 0.0
    remaining = edges
    while len(remaining) > 0:
        seed = remaining[0]
        similar_mask = deltaE_cie76(seed, remaining) < same_threshold
        frac = float(similar_mask.sum()) / total
        if frac > best_frac:
            best_frac = frac
            best_color = remaining[similar_mask].mean(axis=0).astype(np.float32)
        remaining = remaining[~similar_mask]
    return best_color, best_frac


# ── Palette quantization in Lab ───────────────────────────────────

def _build_palette_quantizer(
    image_lab: np.ndarray,
    bg_lab: np.ndarray,
    max_colors: int,
    bg_match_threshold: float,
    palette_merge_threshold: float,
):
    """Return (palette_lab, apply_fn). The palette always contains bg_lab, so
    any pixel whose nearest palette entry is bg snaps to bg → clean alpha.

    Two thresholds matter here: pixels within bg_match_threshold of bg are
    excluded from clustering (so near-bg drift doesn't anchor its own
    centroid and then re-survive as a "not-quite-bg" palette entry).
    Sprite palette entries within palette_merge_threshold of each other are
    collapsed so the sprite doesn't fragment into near-duplicate hues."""
    from sklearn.cluster import KMeans
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.neighbors import KDTree

    flat = image_lab.reshape(-1, 3)
    not_bg = deltaE_cie76(flat, bg_lab) > bg_match_threshold
    foreground = flat[not_bg]

    if foreground.shape[0] == 0:
        palette = bg_lab.reshape(1, 3).astype(np.float32)
    else:
        unique_fg = np.unique(foreground, axis=0)
        target = max(1, max_colors - 1)
        if unique_fg.shape[0] <= target:
            palette = unique_fg.astype(np.float32)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                km = KMeans(n_clusters=target, random_state=42, n_init=10)
                km.fit(unique_fg)
            palette = km.cluster_centers_.astype(np.float32)
        palette = _merge_near_duplicates(palette, palette_merge_threshold)
        # Drop any surviving palette entry that's still inside the bg match
        # radius — k-means can still produce centroids a hair outside the
        # exclusion zone that drift back in after merging.
        to_bg = deltaE_cie76(palette, bg_lab) <= bg_match_threshold
        if to_bg.any():
            palette = palette[~to_bg]
        palette = np.vstack([palette, bg_lab.reshape(1, 3)]).astype(np.float32)

    tree = KDTree(palette, leaf_size=8)

    def apply(img_lab: np.ndarray) -> np.ndarray:
        shape = img_lab.shape
        flat = img_lab.reshape(-1, 3)
        _, idx = tree.query(flat)
        mapped = palette[idx.ravel()]
        # Anything that resolved to within bg_match of bg → exactly bg.
        # This is what collapses fringe into the transparent class by construction.
        near_bg = deltaE_cie76(mapped, bg_lab) <= bg_match_threshold
        mapped[near_bg] = bg_lab
        return mapped.reshape(shape)

    return palette, apply


def _merge_near_duplicates(palette: np.ndarray, threshold: float) -> np.ndarray:
    """Iteratively drop one of every pair whose ΔE is below threshold."""
    p = palette.copy()
    while p.shape[0] > 2:
        a = np.repeat(p[:, None, :], p.shape[0], axis=1).reshape(-1, 3)
        b = np.tile(p, (p.shape[0], 1))
        d = deltaE_cie76(a, b).reshape(p.shape[0], p.shape[0])
        np.fill_diagonal(d, np.inf)
        if float(d.min()) > threshold:
            break
        idx = int(np.argmin(d))
        i, j = divmod(idx, p.shape[0])
        p = np.delete(p, max(i, j), axis=0)
    return p


# ── Edge profile & grid recovery ──────────────────────────────────

def _edge_profile(image_lab: np.ndarray, axis: int) -> np.ndarray:
    """1D profile of perceptual color-change along `axis`. axis=0 gives width-profile."""
    arr = image_lab if axis == 0 else np.swapaxes(image_lab, 0, 1)
    delta = deltaE_cie76(arr[:, :-1], arr[:, 1:], channel_axis=2)
    active = (np.abs(delta) > 0).astype(np.float32)
    active = np.hstack([active, np.zeros((active.shape[0], 1), dtype=np.float32)])
    profile = active.mean(axis=0)
    m = profile.max()
    if m > 0:
        profile = profile / m
    return profile


def _spacing_error(
    spacing: float,
    sorted_peaks: np.ndarray,
    limit: int,
    gap_weight: float = 1.0,
) -> float:
    """RMSE of inter-peak distances to integer multiples of spacing, plus a
    penalty for implied missing peaks. Lower is better."""
    if spacing <= 0 or len(sorted_peaks) < 2:
        return float("inf")
    diffs = np.diff(sorted_peaks).astype(np.float64)
    expected = np.maximum(1.0, np.round(diffs / spacing))
    expected_d = expected * spacing
    sq_err = float(np.sum((diffs - expected_d) ** 2))
    rmse = float(np.sqrt(sq_err / len(diffs)))

    gaps = int(np.sum(np.maximum(0, expected - 1)))
    total_expected = int(np.sum(expected))

    before = max(0.0, float(sorted_peaks[0]))
    after = max(0.0, float(limit) - float(sorted_peaks[-1]))
    outside = int(round((before + after) / spacing))
    gaps += outside
    total_expected += outside

    gap_penalty = (gaps / total_expected * gap_weight) if total_expected > 0 else 0.0
    return rmse / spacing + gap_penalty


def _find_best_spacing(
    peaks: np.ndarray,
    prominences: np.ndarray,
    limit: int,
    min_peaks: int,
    max_pixel_size: int,
    coarser_bias: float = 0.15,
) -> float:
    """Try using top-K peaks (K from min_peaks upward) and optimize spacing for each.

    The raw error landscape is nearly flat across K — a spacing of 4 fits almost
    any peak set, producing low but meaningless error. We bias toward coarser
    grids: any candidate whose error is within `coarser_bias` of the best gets
    considered, and we pick the largest spacing among those. This corrects the
    "over-subdivided" outputs where each real AI-pixel becomes 2×2 output cells."""
    if len(peaks) < min_peaks:
        return 0.0
    order = np.argsort(-prominences)
    peaks_by_strength = peaks[order]

    candidates: list[tuple[float, float]] = []  # (spacing, error)
    for k in range(min_peaks, len(peaks_by_strength) + 1):
        top_k = np.sort(peaks_by_strength[:k])
        if len(top_k) < 2:
            continue
        init = float(np.median(np.diff(top_k)))
        lo, hi = 1.0, float(max_pixel_size)
        if not (lo < init < hi):
            init = float(np.clip(init, lo + 1e-6, hi - 1e-6))
        res = minimize_scalar(
            lambda s: _spacing_error(float(s), top_k, limit),
            bounds=(lo, hi),
            method="bounded",
            options={"xatol": 1e-3},
        )
        if not res.success:
            continue
        candidates.append((float(res.x), float(res.fun)))

    if not candidates:
        return 0.0

    best_err = min(c[1] for c in candidates)
    acceptable = [c for c in candidates if c[1] <= best_err * (1.0 + coarser_bias)]
    # Among acceptable-error candidates, pick the largest spacing.
    return max(acceptable, key=lambda c: c[0])[0]


def _place_cut_lines(
    peaks: np.ndarray,
    prominences: np.ndarray,
    spacing: float,
    cell_trim: float = 0.7,
    gap_fill: float = 1.5,
) -> np.ndarray:
    """Use prominences to greedily keep the best peak per cell-width, then fill
    large gaps with evenly-spaced synthetic cuts. Returns cut positions (float)."""
    if len(peaks) == 0 or spacing <= 0:
        return np.array([], dtype=np.float32)

    order = np.argsort(-prominences)
    peaks_s = peaks[order]
    proms_s = prominences[order]

    trim_dist = spacing * cell_trim
    kept: list[tuple[float, float]] = []
    for x, p in zip(peaks_s.astype(float), proms_s.astype(float)):
        suppress = False
        for kx, kp in kept:
            if abs(x - kx) <= trim_dist and p <= kp:
                suppress = True
                break
        if not suppress:
            kept.append((x, p))

    kept_x = np.sort(np.array([x for x, _ in kept], dtype=np.float32))
    if len(kept_x) == 0:
        return np.array([], dtype=np.float32)

    gap_thresh = spacing * gap_fill
    edges = [float(kept_x[0]) - spacing]
    for i, x in enumerate(kept_x):
        edges.append(float(x))
        if i < len(kept_x) - 1:
            gap = float(kept_x[i + 1] - x)
            if gap > gap_thresh:
                n_insert = int(round(gap / spacing) - 1)
                if n_insert > 0:
                    step = gap / (n_insert + 1)
                    for k in range(n_insert):
                        edges.append(edges[-1] + step)
    edges.append(float(kept_x[-1]) + spacing)
    return np.asarray(edges, dtype=np.float32) + 0.5


# ── Cell sampling ─────────────────────────────────────────────────

def _sample_at_cell_centers(
    image_lab: np.ndarray,
    bg_lab: np.ndarray,
    edges_x: np.ndarray,
    edges_y: np.ndarray,
) -> np.ndarray:
    """Nearest-neighbor lookup at the center of each discovered cell."""
    h, w = image_lab.shape[:2]
    interp = RegularGridInterpolator(
        (np.arange(h), np.arange(w)),
        image_lab,
        method="nearest",
        bounds_error=False,
        fill_value=bg_lab,
    )
    cx = (edges_x[:-1] + edges_x[1:]) * 0.5
    cy = (edges_y[:-1] + edges_y[1:]) * 0.5
    yy, xx = np.meshgrid(cy, cx, indexing="ij")
    pts = np.stack([yy.ravel(), xx.ravel()], axis=-1)
    sampled = interp(pts).reshape(len(cy), len(cx), 3)
    return sampled.astype(np.float32)


# ── Alpha with edge-adjacent fringe cleanup ──────────────────────

def _make_alpha(
    sprite_lab: np.ndarray,
    bg_lab: np.ndarray,
    same_threshold: float,
    border_threshold: float,
    max_peel_passes: int = 4,
    loose_check_lab: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (rgb_float01, alpha_0_or_1). A pixel is transparent if:
      (a) its ΔE to bg is below same_threshold (checked on sprite_lab), OR
      (b) it is adjacent to a transparent pixel AND its ΔE to bg is below
          border_threshold (checked on `loose_check_lab` if provided, else
          on sprite_lab).

    Passing the original (pre-palette) image as `loose_check_lab` is critical
    when the pipeline includes palette quantization: AA edge pixels often
    have RAW colors near bg (dark gray fringing toward black) but get snapped
    to a far-from-bg palette entry, so a sprite_lab-only check misses them.
    Checking adjacency-gated fringe against original Lab catches them.

    Rule (b) is applied iteratively — newly-transparent fringe promotes its
    neighbors into the adjacency ring, so multi-pixel-thick fringe peels away
    ring by ring."""
    delta_strict = deltaE_cie76(sprite_lab, bg_lab)
    is_bg = delta_strict < same_threshold
    delta_loose_src = loose_check_lab if loose_check_lab is not None else sprite_lab
    delta_loose = deltaE_cie76(delta_loose_src, bg_lab)
    loose_candidate = delta_loose < border_threshold
    for _ in range(max_peel_passes):
        ring = binary_dilation(is_bg, disk(1))
        next_bg = is_bg | (ring & loose_candidate)
        if np.array_equal(next_bg, is_bg):
            break
        is_bg = next_bg

    alpha = np.where(is_bg, 0, 1).astype(np.uint8)
    rgb = lab2rgb(sprite_lab).astype(np.float32)
    rgb[is_bg] = 0.0
    return rgb, alpha


# ── Cleanup & symmetry ────────────────────────────────────────────

def _erode_alpha(rgba: np.ndarray, px: int) -> np.ndarray:
    """Erode the binary alpha mask inward by `px` pixels. Strips the outermost
    AA ring where the AI blended subject color with bg color, leaving cleaner
    silhouettes. Run BEFORE any downsampling so 1px corresponds to a tiny
    fraction of an output cell, not a whole AI-pixel."""
    from skimage.morphology import erosion, footprint_rectangle
    if px <= 0:
        return rgba
    alpha = rgba[..., 3] > 0.5
    fp = footprint_rectangle((2 * px + 1, 2 * px + 1))
    eroded = erosion(alpha, fp)
    out = rgba.copy()
    out[~eroded] = 0
    return out


def _keep_largest_region(rgba: np.ndarray) -> np.ndarray:
    """Keep only the single largest connected opaque component. Inspired by
    RetroDiffusion's islands-style extraction: when the generator produces an
    isolated subject, the subject is one big connected blob and any other
    surviving opaque pixels are bg artifacts (gradient remnants, horizon
    stripes, scene elements the color-key couldn't reach). Works regardless
    of whether those artifacts touch the border — so it's safe for subjects
    that legitimately extend to the image edge (banners, wide waves, etc).

    No-op when there's only one component or zero opaque pixels."""
    from skimage.measure import label
    alpha = rgba[..., 3] > 0.5
    if not alpha.any():
        return rgba
    labeled = label(alpha, connectivity=2)
    n_labels = int(labeled.max())
    if n_labels <= 1:
        return rgba
    sizes = np.bincount(labeled.ravel())
    sizes[0] = 0  # background label
    largest = int(sizes.argmax())
    keep_mask = labeled == largest
    out = rgba.copy()
    out[~keep_mask] = 0
    return out


def _cleanup_small_islands(rgba: np.ndarray, dilution: int, min_size: int) -> np.ndarray:
    """Remove disconnected opaque clusters smaller than min_size that aren't
    close (within dilution) to any larger cluster."""
    if min_size <= 0:
        return rgba
    opaque = rgba[..., 3] > 0.5
    pruned = remove_small_objects(opaque, min_size=min_size)
    bridged = binary_dilation(pruned, disk(dilution)) | opaque
    survivors = remove_small_objects(bridged, min_size=min_size)
    kill = opaque & ~survivors
    rgba[kill] = 0
    return rgba


def _axis_symmetry(gray: np.ndarray) -> tuple[int, float]:
    """Find the index of strongest self-correlation with horizontal reflection,
    averaged per row. Returns (center_index, mean_correlation)."""
    h, w = gray.shape
    if h == 0 or w == 0:
        return 0, 0.0
    acc = np.zeros(w, dtype=np.float32)
    for y in range(h):
        row = gray[y].astype(np.float32)
        rev = row[::-1]
        denom_r = float(row.std()) * row.size
        denom_q = float(rev.std())
        if denom_r == 0.0 or denom_q == 0.0:
            continue
        a = (row - row.mean()) / denom_r
        b = (rev - rev.mean()) / denom_q
        acc += np.correlate(a, b, mode="same")
    acc /= max(h, 1)
    idx = int(acc.argmax())
    return idx, float(acc[idx])


def _pad_to_center(rgba: np.ndarray, target: float, axis: int) -> np.ndarray:
    current = rgba.shape[axis] / 2.0
    shift = int(target - current)
    if shift == 0:
        return rgba
    pad = [(0, 0)] * rgba.ndim
    pad[axis] = (max(0, -shift), max(0, shift))
    return np.pad(rgba, pad, mode="constant", constant_values=0)


# ── Splitting multi-sprite images ─────────────────────────────────

def _split_subregions(
    image_lab: np.ndarray,
    bg_lab: np.ndarray,
    same_threshold: float,
    min_distance: int,
) -> list[np.ndarray]:
    """Dilate-then-label to find connected non-bg blobs separated by ≥ min_distance."""
    from skimage.measure import label, regionprops

    delta = deltaE_cie76(image_lab, bg_lab)
    opaque = delta > same_threshold
    dilated = binary_dilation(opaque, disk(min_distance))
    labeled = label(dilated)
    regions = []
    for r in regionprops(labeled):
        y0, x0, y1, x1 = r.bbox
        regions.append(image_lab[y0:y1, x0:x1])
    return regions


def _crop_to_non_bg(
    image_lab: np.ndarray,
    bg_lab: np.ndarray,
    same_threshold: float,
    padding: int = 5,
) -> np.ndarray:
    delta = deltaE_cie76(image_lab, bg_lab)
    mask = delta > same_threshold
    if not mask.any():
        return image_lab
    ys, xs = np.where(mask)
    y0 = max(int(ys.min()) - padding, 0)
    y1 = min(int(ys.max()) + padding + 1, image_lab.shape[0])
    x0 = max(int(xs.min()) - padding, 0)
    x1 = min(int(xs.max()) + padding + 1, image_lab.shape[1])
    return image_lab[y0:y1, x0:x1]


# ── Per-region pipeline ───────────────────────────────────────────

def _extract_one(
    image_lab: np.ndarray,
    bg_lab: np.ndarray,
    config: ExtractConfig,
) -> Optional[ExtractedSprite]:
    region = _crop_to_non_bg(image_lab, bg_lab, config.bg_match_threshold)
    if min(region.shape[:2]) < 4:
        return None

    _, apply_palette = _build_palette_quantizer(
        region,
        bg_lab,
        config.max_palette_colors,
        config.bg_match_threshold,
        config.palette_merge_threshold,
    )
    indexed = apply_palette(region)

    profile_x = _edge_profile(indexed, axis=0)
    profile_y = _edge_profile(indexed, axis=1)
    if config.profile_smooth_sigma > 0:
        profile_x = gaussian_filter1d(profile_x, sigma=config.profile_smooth_sigma)
        profile_y = gaussian_filter1d(profile_y, sigma=config.profile_smooth_sigma)

    peaks_x, _ = find_peaks(profile_x)
    peaks_y, _ = find_peaks(profile_y)
    if len(peaks_x) < config.min_peaks_required or len(peaks_y) < config.min_peaks_required:
        return None
    proms_x = peak_prominences(profile_x, peaks_x)[0]
    proms_y = peak_prominences(profile_y, peaks_y)[0]

    min_px = max(3, int(len(peaks_x) * config.min_peak_fraction))
    min_py = max(3, int(len(peaks_y) * config.min_peak_fraction))
    spacing_x = _find_best_spacing(
        peaks_x, proms_x, profile_x.shape[0], min_px, config.max_pixel_size, config.coarser_grid_bias
    )
    spacing_y = _find_best_spacing(
        peaks_y, proms_y, profile_y.shape[0], min_py, config.max_pixel_size, config.coarser_grid_bias
    )
    if spacing_x <= 0 or spacing_y <= 0:
        return None

    # Symmetric-grid enforcement. AI pixel art is drawn on square cells;
    # per-axis spacing estimates disagree either from measurement noise on
    # square inputs, or from the generator drawing fewer cells across the
    # long axis on rectangular inputs (so X-spacing balloons while Y-spacing
    # stays sensible). In both cases the correct per-pixel size is the
    # estimate from the MINOR (shorter) axis of the region — that gives a
    # banner the same pixel density as a square of the same height.
    _h, _w = region.shape[:2]
    if _h < _w:
        spacing_x = spacing_y   # wide: height drives
    elif _w < _h:
        spacing_y = spacing_x   # tall: width drives
    else:
        # Exactly square: use the per-axis average when they agree, else
        # take the smaller (preserves finer pixel structure).
        _ratio = max(spacing_x, spacing_y) / max(min(spacing_x, spacing_y), 1e-6)
        if _ratio < 1.3:
            _avg = (spacing_x + spacing_y) / 2.0
            spacing_x = spacing_y = _avg
        else:
            spacing_x = spacing_y = min(spacing_x, spacing_y)

    edges_x = _place_cut_lines(peaks_x, proms_x, spacing_x)
    edges_y = _place_cut_lines(peaks_y, proms_y, spacing_y)
    if len(edges_x) < 2 or len(edges_y) < 2:
        return None

    sprite_lab = _sample_at_cell_centers(region, bg_lab, edges_x, edges_y)

    # Tighter second-pass quantization on the already-sampled sprite — this
    # locks every pixel to one of K palette colors, including exact bg for fringe.
    _, apply_sprite_palette = _build_palette_quantizer(
        sprite_lab,
        bg_lab,
        config.max_palette_colors,
        config.bg_match_threshold,
        config.palette_merge_threshold,
    )
    sprite_lab = apply_sprite_palette(sprite_lab)

    gray = rgb2gray(lab2rgb(sprite_lab))
    cx, xr = _axis_symmetry(gray)
    cy, yr = _axis_symmetry(gray.T)

    rgb, alpha = _make_alpha(
        sprite_lab, bg_lab, config.bg_match_threshold, config.border_fringe_threshold
    )
    rgba = np.dstack([rgb, alpha.astype(np.float32)])
    rgba = _cleanup_small_islands(rgba, config.land_dilution, config.island_size)

    if rgba.shape[0] < config.min_sprite_size and rgba.shape[1] < config.min_sprite_size:
        return None

    centered_x = xr > config.symmetry_threshold
    centered_y = yr > config.symmetry_threshold
    if centered_x:
        rgba = _pad_to_center(rgba, cx, axis=1)
    if centered_y:
        rgba = _pad_to_center(rgba, cy, axis=0)

    rgba_u8 = np.rint(np.clip(rgba, 0.0, 1.0) * 255.0).astype(np.uint8)

    return ExtractedSprite(
        rgba=rgba_u8,
        pixel_size_x=float(spacing_x),
        pixel_size_y=float(spacing_y),
        centered_x=centered_x,
        centered_y=centered_y,
    )
