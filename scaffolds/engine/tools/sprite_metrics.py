"""Per-metric inspectors — each (image, metadata?) → float ∈ [0, 1].

Metric functions are declarative: they read the image, extract one
quality signal, and return a normalized score. Higher is better.
Combined into final scores by sprite_scorers via weighted sum.

v1.1 has ~22 metrics grouped by category. Most are 10–30 LOC of
numpy / scipy; nothing CV-heavy. Implementations favor speed +
simplicity over perceptual accuracy — these are filters on generated
images, not ground-truth labels.
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
from PIL import Image

# ─── Shared helpers ──────────────────────────────────────────────────

def _rgba(img: Image.Image) -> np.ndarray:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def _opaque_mask(img: Image.Image, threshold: int = 128) -> np.ndarray:
    return _rgba(img)[:, :, 3] > threshold


def _opaque_rgb(img: Image.Image) -> np.ndarray:
    arr = _rgba(img)
    mask = arr[:, :, 3] > 128
    return arr[mask][:, :3] if mask.any() else np.zeros((0, 3), dtype=np.uint8)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(max(lo, min(hi, x)))


# ─── Shape / composition metrics ─────────────────────────────────────

def coverage(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Opaque fraction of the frame. Ideal: 0.15..0.85 (not too small,
    not bleed-to-edge). Tapered curve; linear ramp to full at 0.15,
    linear drop above 0.85."""
    mask = _opaque_mask(img)
    if mask.size == 0:
        return 0.0
    frac = float(mask.sum()) / float(mask.size)
    if frac < 0.05:
        return 0.0
    if frac < 0.15:
        return frac / 0.15
    if frac > 0.85:
        return _clamp(1.0 - (frac - 0.85) / 0.15)
    return 1.0


def centering(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Center-of-mass offset from frame center (1 = centered, 0 = edge)."""
    from scipy import ndimage
    mask = _opaque_mask(img)
    if not mask.any():
        return 0.0
    com = ndimage.center_of_mass(mask)
    h, w = mask.shape
    cx_off = abs(com[1] / w - 0.5) * 2
    cy_off = abs(com[0] / h - 0.5) * 2
    return _clamp(1.0 - max(cx_off, cy_off))


def fragmentation(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """1 / n_connected_components. 1 blob → 1.0, 5 → 0.2, etc."""
    from scipy import ndimage
    mask = _opaque_mask(img)
    if not mask.any():
        return 0.0
    _, n = ndimage.label(mask)
    return 1.0 / float(max(n, 1))


def silhouette(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Silhouette cleanness: ratio of opaque-bbox area to opaque-mask
    area. 1.0 = perfectly-filled bbox (boring rectangle); 0.5 = half-
    filled (typical character). We favor 0.4..0.8 — punishes both
    blob-like and rectangle-like shapes."""
    arr = _rgba(img)
    alpha = arr[:, :, 3]
    mask = alpha > 128
    if not mask.any():
        return 0.0
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    bbox_area = (rmax - rmin + 1) * (cmax - cmin + 1)
    if bbox_area == 0:
        return 0.0
    fill_ratio = mask.sum() / bbox_area
    # Triangular window around 0.6 — 0 at 0, 1 at 0.6, 0 at 1.0.
    return _clamp(1.0 - abs(fill_ratio - 0.6) / 0.6)


# ─── Color metrics ───────────────────────────────────────────────────

def color_diversity(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Unique color count (on opaque pixels) / 10, clipped to 1."""
    rgb = _opaque_rgb(img)
    if len(rgb) < 10:
        return 0.0
    unique = len(np.unique(rgb.reshape(-1, 3), axis=0))
    return _clamp(unique / 10.0)


def palette_coherence(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Inverse of color entropy — tight palettes score high. Useful for
    tilesets / ui where a small consistent palette is desired."""
    rgb = _opaque_rgb(img)
    if len(rgb) < 10:
        return 0.0
    unique, counts = np.unique(rgb.reshape(-1, 3), axis=0, return_counts=True)
    if len(unique) <= 1:
        return 1.0
    probs = counts / counts.sum()
    entropy = float(-(probs * np.log2(probs + 1e-12)).sum())
    # Normalize entropy by log2(16) — our target palette — then invert
    # so low-entropy (coherent) palettes map to high scores.
    return _clamp(1.0 - entropy / np.log2(16))


def flatness(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """How 'flat' (few color gradients) the sprite is — UI should be
    near-flat. Measure: fraction of neighbor pixels that share an
    exact RGB value."""
    arr = _rgba(img)
    rgb = arr[:, :, :3]
    # Horizontal neighbor equality.
    same = (rgb[:, 1:, :] == rgb[:, :-1, :]).all(axis=2)
    return _clamp(float(same.mean()))


def contrast(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Luminance range across opaque pixels; UI/portrait benefit from
    readable contrast. Normalized by 255 so max range = 1.0."""
    rgb = _opaque_rgb(img)
    if len(rgb) < 4:
        return 0.0
    lum = 0.299 * rgb[:, 0] + 0.587 * rgb[:, 1] + 0.114 * rgb[:, 2]
    return _clamp(float(lum.max() - lum.min()) / 255.0)


def opacity(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Fraction of alpha channel that's non-zero. Mostly-transparent
    sprites (something went wrong) score low."""
    arr = _rgba(img)
    alpha = arr[:, :, 3]
    return _clamp(float((alpha > 0).mean()))


def color_warmth(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Red + yellow dominance vs blue — effect sprites typically warm-
    biased (fire, sparks). (R+G/2 - B) / 255, clipped."""
    rgb = _opaque_rgb(img)
    if len(rgb) == 0:
        return 0.0
    warmth = float(rgb[:, 0].mean() + rgb[:, 1].mean() / 2 - rgb[:, 2].mean()) / 255.0
    return _clamp(warmth * 2.0)  # scale for useful spread


def brightness_range(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Effect sprites need bright core + darker edges for punch."""
    rgb = _opaque_rgb(img)
    if len(rgb) < 10:
        return 0.0
    lum = 0.299 * rgb[:, 0] + 0.587 * rgb[:, 1] + 0.114 * rgb[:, 2]
    p5, p95 = np.percentile(lum, [5, 95])
    return _clamp(float(p95 - p5) / 200.0)


# ─── Tileset-specific ────────────────────────────────────────────────

def tile_count(img: Image.Image, meta: Optional[dict] = None) -> float:
    """1.0 if the runtime atlas tile count matches metadata.tile_grid,
    else linear falloff."""
    if not meta:
        return 0.5
    expected = (int(meta.get("tile_grid_w") or 4)
                * int(meta.get("tile_grid_h") or 4))
    actual = int(meta.get("atlas_tile_count") or expected)
    if expected == 0:
        return 0.0
    return _clamp(1.0 - abs(expected - actual) / expected)


def tileability(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Single-image tileability — L/R + T/B edge-RGB similarity,
    averaged. Sub-pixel perfect tiling scores ~1; random image ~0."""
    arr = _rgba(img)
    rgb = arr[:, :, :3].astype(float)
    left, right = rgb[:, 0, :], rgb[:, -1, :]
    top, bot = rgb[0, :, :], rgb[-1, :, :]
    h_dist = float(np.mean(np.abs(left - right))) / 255.0
    v_dist = float(np.mean(np.abs(top - bot))) / 255.0
    return _clamp(1.0 - (h_dist + v_dist) / 2.0)


def seamlessness(img: Image.Image, meta: Optional[dict] = None) -> float:
    """Fraction of per-tile seamless flags that are True. Reads from
    metadata['per_tile_seamless'] written by seamless_check op."""
    if not meta or "per_tile_seamless" not in meta:
        return 0.5
    entries = meta["per_tile_seamless"]
    if not entries:
        return 0.0
    # Tile counts as seamless when both h and v pass.
    n_seamless = sum(
        1 for e in entries
        if e.get("seamless_h") and e.get("seamless_v")
    )
    return _clamp(n_seamless / len(entries))


def per_tile_coverage(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Use the sheet-level opaque fraction as a proxy for per-tile
    coverage. A well-populated tile sheet should have most tiles
    well-covered."""
    return coverage(img)


def edge_fringe(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Low semi-transparent fringe = good. Measures the fraction of
    alpha in [10..245] vs fully-opaque. Inverted: small = good → 1.0."""
    arr = _rgba(img)
    alpha = arr[:, :, 3]
    edge = ((alpha > 10) & (alpha < 245)).mean()
    return _clamp(1.0 - float(edge) * 4.0)  # scale so ~25% fringe → 0


# ─── Background-specific ─────────────────────────────────────────────

def aspect_fidelity(img: Image.Image, meta: Optional[dict] = None) -> float:
    """Rendered aspect vs desired aspect. Defaults to 16:9 when no
    metadata target is set (typical background)."""
    target_aspect = float((meta or {}).get("aspect", 16 / 9))
    w, h = img.size
    if h == 0:
        return 0.0
    actual = w / h
    return _clamp(1.0 - abs(actual - target_aspect) / max(target_aspect, 1e-6))


def seamless_horizontal(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Left vs right edge RGB similarity. 1.0 = perfect horizontal
    tile."""
    arr = _rgba(img)[:, :, :3].astype(float)
    left, right = arr[:, 0, :], arr[:, -1, :]
    h_dist = float(np.mean(np.abs(left - right))) / 255.0
    return _clamp(1.0 - h_dist)


def no_dominant_subject(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Backgrounds shouldn't have a single large opaque blob at center.
    Inverse of normalized center-of-mass dominance."""
    from scipy import ndimage
    mask = _opaque_mask(img)
    if not mask.any():
        return 1.0
    _, n = ndimage.label(mask)
    # Many small regions = good (diffuse background).
    # One giant region at the center = bad (subject detected).
    if n == 0:
        return 1.0
    if n >= 5:
        return 1.0
    return _clamp(n / 5.0)


# ─── UI-specific ─────────────────────────────────────────────────────

def clean_edges(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Sharp alpha step — UI elements shouldn't have gradient edges.
    Inverse of fraction of mid-alpha pixels."""
    return edge_fringe(img)


# ─── Effect-specific ─────────────────────────────────────────────────

def radial_coherence(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Effect sprites should brighten toward center. Correlate
    luminance with inverse radius."""
    arr = _rgba(img)
    rgb = arr[:, :, :3].astype(float)
    alpha = arr[:, :, 3].astype(float) / 255.0
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    cy, cx = h / 2, w / 2
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    rmax = float(r.max()) if r.max() > 0 else 1.0
    inv_r = 1.0 - r / rmax
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    weighted_lum = lum * alpha
    if alpha.sum() < 10:
        return 0.0
    # Pearson correlation — high positive = effect-shaped.
    flat_l = weighted_lum.ravel()
    flat_r = inv_r.ravel()
    if flat_l.std() < 1e-6 or flat_r.std() < 1e-6:
        return 0.5
    rho = float(np.corrcoef(flat_l, flat_r)[0, 1])
    return _clamp((rho + 1.0) / 2.0)


def no_unwanted_subject(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Effect sprites should be diffuse, not contain a crisp subject.
    Use inverse silhouette: high silhouette-score → low effect score."""
    return _clamp(1.0 - silhouette(img))


# ─── Portrait-specific ───────────────────────────────────────────────

def eye_detection(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Heuristic: presence of two dark-pixel clusters in the upper
    third of the opaque region. Cheap proxy for 'has eyes'."""
    from scipy import ndimage
    arr = _rgba(img)
    alpha = arr[:, :, 3]
    mask = alpha > 128
    if not mask.any():
        return 0.0
    rows = np.where(np.any(mask, axis=1))[0]
    if len(rows) < 4:
        return 0.0
    rmin, rmax = rows[0], rows[-1]
    upper = (rmin, rmin + (rmax - rmin) // 3)
    region = arr[upper[0]:upper[1], :, :]
    if region.size == 0:
        return 0.0
    rgb = region[:, :, :3].astype(float)
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    # Dark-pixel mask within upper third.
    dark = (lum < 80) & (region[:, :, 3] > 128)
    if not dark.any():
        return 0.0
    _, n = ndimage.label(dark)
    # 2 clusters = ideal; 0 or many = worse.
    return _clamp(1.0 - abs(n - 2) / 3.0)


def head_proportion(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Opaque-region aspect ~1:1 is ideal portrait. Very tall or wide
    shapes score lower."""
    mask = _opaque_mask(img)
    if not mask.any():
        return 0.0
    rows = np.any(mask, axis=1); cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    dh = rmax - rmin + 1
    dw = cmax - cmin + 1
    aspect = dw / max(dh, 1)
    return _clamp(1.0 - abs(aspect - 1.0))


def no_text(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Absence-of-text heuristic: high frequency horizontal edges
    (characteristic of text) penalty. Simple Sobel-y magnitude check."""
    from scipy import ndimage
    arr = _rgba(img)
    rgb = arr[:, :, :3].astype(float).mean(axis=2)
    sy = ndimage.sobel(rgb, axis=0)
    # Count rows with very high horizontal-edge density.
    edge_rows = (np.abs(sy) > 80).mean(axis=1)
    dense = (edge_rows > 0.3).sum()
    return _clamp(1.0 - dense / 10.0)


def clean_silhouette(img: Image.Image, _meta: Optional[dict] = None) -> float:
    """Combines fragmentation + edge_fringe for a portrait-specific
    'is this outline believable' score."""
    return (fragmentation(img) + edge_fringe(img)) / 2.0


# ─── Metric registry ─────────────────────────────────────────────────

METRICS: dict[str, callable] = {
    "coverage":              coverage,
    "centering":             centering,
    "fragmentation":         fragmentation,
    "silhouette":            silhouette,
    "color_diversity":       color_diversity,
    "palette_coherence":     palette_coherence,
    "flatness":              flatness,
    "contrast":              contrast,
    "opacity":               opacity,
    "color_warmth":          color_warmth,
    "brightness_range":      brightness_range,
    "tile_count":            tile_count,
    "tileability":           tileability,
    "seamlessness":          seamlessness,
    "per_tile_coverage":     per_tile_coverage,
    "edge_fringe":           edge_fringe,
    "aspect_fidelity":       aspect_fidelity,
    "seamless_horizontal":   seamless_horizontal,
    "no_dominant_subject":   no_dominant_subject,
    "clean_edges":           clean_edges,
    "radial_coherence":      radial_coherence,
    "no_unwanted_subject":   no_unwanted_subject,
    "eye_detection":         eye_detection,
    "head_proportion":       head_proportion,
    "no_text":               no_text,
    "clean_silhouette":      clean_silhouette,
}


def compute_metric(
    name: str,
    img: Image.Image,
    metadata: Optional[dict[str, Any]] = None,
) -> float:
    """Dispatch to a metric fn by name. Unknown → 0.0 (so scorers
    degrade gracefully when a metric isn't wired yet)."""
    fn = METRICS.get(name)
    if fn is None:
        return 0.0
    try:
        return float(fn(img, metadata))
    except Exception:
        # Metrics shouldn't crash the pipeline; surface as a low score
        # so the caller still gets a complete score dict.
        return 0.0
