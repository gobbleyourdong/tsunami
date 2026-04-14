"""
Pixel-perfect grid recovery for AI-generated pixel art.

AI models don't generate on a consistent pixel grid — their "pixels" drift in
size and position across the image. Naive nearest-neighbor downscaling smears
this drift. This module discovers the native grid *from the image itself* by
analyzing gradient profiles along each axis, then mode-resamples each cell.

Ported from github.com/Hugo-Dz/spritefusion-pixel-snapper (MIT, Hugo Duprez).

Pipeline:
  1. K-means color quantization (sharpens grid edges)
  2. Per-axis luma-gradient profiles
  3. Peak analysis → native pixel step-size per axis
  4. Elastic walker emits cut lines, snapping to local gradient maxima
  5. Cross-axis stabilization (forces near-square cells when axes disagree)
  6. Mode-resample each cell — preserves dithering, rejects anti-aliasing
"""

from __future__ import annotations

import numpy as np
from PIL import Image

DEFAULTS = dict(
    k_colors=16,
    k_seed=42,
    max_kmeans_iterations=15,
    peak_threshold_multiplier=0.2,
    peak_distance_filter=4,
    walker_search_window_ratio=0.35,
    walker_min_search_window=2.0,
    walker_strength_threshold=0.5,
    min_cuts_per_axis=4,
    fallback_target_segments=64,
    max_step_ratio=1.8,
)


def snap_to_grid(img: Image.Image, k_colors: int = 16, **overrides) -> Image.Image:
    """Recover the native pixel grid and downscale to it.

    Output dimensions are determined by the discovered grid, not by any
    target size — a 512×512 AI image with ~8px AI-pixels yields ~64×64 out.
    Caller can nearest-neighbor resize afterward if a fixed size is needed.
    """
    cfg = {**DEFAULTS, **overrides, "k_colors": k_colors}
    arr = np.asarray(img.convert("RGBA"))
    h, w = arr.shape[:2]
    if w < 3 or h < 3:
        return img.copy()

    quantized = _quantize(arr, cfg)
    prof_x, prof_y = _gradient_profiles(quantized)

    step_x = _estimate_step(prof_x, cfg)
    step_y = _estimate_step(prof_y, cfg)
    step_x, step_y = _resolve_steps(step_x, step_y, w, h, cfg)

    raw_cols = _walk(prof_x, step_x, w, cfg)
    raw_rows = _walk(prof_y, step_y, h, cfg)
    cols, rows = _stabilize(prof_x, prof_y, raw_cols, raw_rows, w, h, cfg)

    out = _resample(quantized, cols, rows)
    return Image.fromarray(out)


# ── K-means++ quantization ────────────────────────────────────────

def _quantize(arr: np.ndarray, cfg: dict) -> np.ndarray:
    """K-means++ color quantization on opaque pixels only. Returns RGBA uint8."""
    k = cfg["k_colors"]
    if k <= 0:
        raise ValueError("k_colors must be > 0")

    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3].astype(np.float32)
    opaque_mask = alpha > 0
    opaque = rgb[opaque_mask]  # (N, 3)
    n = len(opaque)
    if n == 0:
        return arr.copy()

    k = min(k, n)
    rng = np.random.default_rng(cfg["k_seed"])

    # k-means++ seeding
    centroids = np.empty((k, 3), dtype=np.float32)
    centroids[0] = opaque[rng.integers(0, n)]
    distances = np.full(n, np.inf, dtype=np.float32)
    for i in range(1, k):
        d = np.sum((opaque - centroids[i - 1]) ** 2, axis=1)
        distances = np.minimum(distances, d)
        total = float(distances.sum())
        if total <= 0.0:
            centroids[i] = opaque[rng.integers(0, n)]
        else:
            centroids[i] = opaque[rng.choice(n, p=distances / total)]

    # Lloyd iterations
    prev = centroids.copy()
    for it in range(cfg["max_kmeans_iterations"]):
        d2 = np.sum((opaque[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
        labels = np.argmin(d2, axis=1)
        for ki in range(k):
            m = labels == ki
            if m.any():
                centroids[ki] = opaque[m].mean(axis=0)
        if it > 0:
            if np.max(np.sum((centroids - prev) ** 2, axis=1)) < 0.01:
                break
        prev = centroids.copy()

    # Final assignment
    d2 = np.sum((opaque[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
    labels = np.argmin(d2, axis=1)
    snapped = np.clip(np.round(centroids[labels]), 0, 255).astype(np.uint8)

    out = arr.copy()
    out_rgb = out[:, :, :3].copy()
    out_rgb[opaque_mask] = snapped
    out[:, :, :3] = out_rgb
    return out


# ── Gradient profiles ─────────────────────────────────────────────

def _gradient_profiles(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Luma-gradient projections along each axis using a [-1, 0, 1] kernel.
    Transparent pixels contribute 0 (treated as grayscale 0)."""
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3].astype(np.float64)
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    gray = np.where(alpha == 0, 0.0, gray)

    h, w = gray.shape
    col_proj = np.zeros(w)
    col_proj[1:-1] = np.abs(gray[:, 2:] - gray[:, :-2]).sum(axis=0)
    row_proj = np.zeros(h)
    row_proj[1:-1] = np.abs(gray[2:, :] - gray[:-2, :]).sum(axis=1)
    return col_proj, row_proj


# ── Step-size estimation ──────────────────────────────────────────

def _estimate_step(profile: np.ndarray, cfg: dict) -> float | None:
    """Find periodicity in the gradient profile. Returns None if no reliable estimate."""
    if len(profile) == 0:
        return None
    max_val = float(profile.max())
    if max_val == 0.0:
        return None

    threshold = max_val * cfg["peak_threshold_multiplier"]
    # Strict local maxima above threshold
    peaks: list[int] = []
    for i in range(1, len(profile) - 1):
        if profile[i] > threshold and profile[i] > profile[i - 1] and profile[i] > profile[i + 1]:
            peaks.append(i)
    if len(peaks) < 2:
        return None

    # Drop peaks closer than peak_distance_filter
    min_gap = cfg["peak_distance_filter"] - 1
    clean = [peaks[0]]
    for p in peaks[1:]:
        if p - clean[-1] > min_gap:
            clean.append(p)
    if len(clean) < 2:
        return None

    return float(np.median(np.diff(clean)))


def _resolve_steps(sx, sy, w: int, h: int, cfg: dict) -> tuple[float, float]:
    """Reconcile per-axis step estimates. Falls back to image-wide segmentation."""
    mx = cfg["max_step_ratio"]
    if sx is not None and sy is not None:
        ratio = max(sx / sy, sy / sx)
        if ratio > mx:
            s = min(sx, sy)
            return s, s
        avg = (sx + sy) / 2.0
        return avg, avg
    if sx is not None:
        return sx, sx
    if sy is not None:
        return sy, sy
    fb = max(min(w, h) / cfg["fallback_target_segments"], 1.0)
    return fb, fb


# ── Elastic walker ────────────────────────────────────────────────

def _walk(profile: np.ndarray, step: float, limit: int, cfg: dict) -> list[int]:
    """March across the profile at `step`, snapping each cut to the strongest
    gradient within a search window. Falls through to uniform spacing when
    the local gradient is too weak."""
    if len(profile) == 0:
        raise ValueError("cannot walk on empty profile")

    cuts = [0]
    pos = 0.0
    window = max(step * cfg["walker_search_window_ratio"], cfg["walker_min_search_window"])
    mean_val = float(profile.mean())
    threshold = mean_val * cfg["walker_strength_threshold"]

    while pos < limit:
        target = pos + step
        if target >= limit:
            cuts.append(limit)
            break
        start = max(int(target - window), int(pos + 1.0))
        end = min(int(target + window), limit)
        if end <= start:
            pos = target
            continue
        sub = profile[start:end]
        max_idx = start + int(np.argmax(sub))
        max_val = float(profile[max_idx])
        if max_val > threshold:
            cuts.append(max_idx)
            pos = float(max_idx)
        else:
            cuts.append(int(target))
            pos = target
    return cuts


# ── Stabilization ─────────────────────────────────────────────────

def _stabilize(
    prof_x: np.ndarray,
    prof_y: np.ndarray,
    raw_cols: list[int],
    raw_rows: list[int],
    w: int,
    h: int,
    cfg: dict,
) -> tuple[list[int], list[int]]:
    """Two-pass stabilization: per-axis cleanup, then cross-axis coherence."""
    cols = _stabilize_axis(prof_x, raw_cols, w, raw_rows, h, cfg)
    rows = _stabilize_axis(prof_y, raw_rows, h, raw_cols, w, cfg)

    col_cells = max(len(cols) - 1, 1)
    row_cells = max(len(rows) - 1, 1)
    col_step = w / col_cells
    row_step = h / row_cells
    ratio = max(col_step / row_step, row_step / col_step)

    if ratio <= cfg["max_step_ratio"]:
        return cols, rows

    # One axis is much coarser than the other — resample it uniformly.
    target = min(col_step, row_step)
    if col_step > target * 1.2:
        cols = _snap_uniform(prof_x, w, target, cfg, cfg["min_cuts_per_axis"])
    if row_step > target * 1.2:
        rows = _snap_uniform(prof_y, h, target, cfg, cfg["min_cuts_per_axis"])
    return cols, rows


def _stabilize_axis(
    profile: np.ndarray,
    cuts: list[int],
    limit: int,
    sibling_cuts: list[int],
    sibling_limit: int,
    cfg: dict,
) -> list[int]:
    if limit == 0:
        return [0]

    cuts = _sanitize_cuts(cuts, limit)
    min_required = max(min(cfg["min_cuts_per_axis"], limit + 1), 2)
    axis_cells = len(cuts) - 1
    sibling_cells = len(sibling_cuts) - 1
    sibling_has_grid = (
        sibling_limit > 0
        and sibling_cells >= max(min_required - 1, 0)
        and sibling_cells > 0
    )
    steps_skewed = False
    if sibling_has_grid and axis_cells > 0:
        axis_step = limit / axis_cells
        sib_step = sibling_limit / sibling_cells
        r = axis_step / sib_step
        steps_skewed = r > cfg["max_step_ratio"] or r < 1.0 / cfg["max_step_ratio"]
    has_enough = len(cuts) >= min_required

    if has_enough and not steps_skewed:
        return cuts

    if sibling_has_grid:
        target_step = sibling_limit / sibling_cells
    elif cfg["fallback_target_segments"] > 1:
        target_step = limit / cfg["fallback_target_segments"]
    elif axis_cells > 0:
        target_step = limit / axis_cells
    else:
        target_step = float(limit)
    if not np.isfinite(target_step) or target_step <= 0.0:
        target_step = 1.0

    return _snap_uniform(profile, limit, target_step, cfg, min_required)


def _sanitize_cuts(cuts: list[int], limit: int) -> list[int]:
    if limit == 0:
        return [0]
    clipped = [min(c, limit) for c in cuts]
    if 0 not in clipped:
        clipped.append(0)
    if limit not in clipped:
        clipped.append(limit)
    return sorted(set(clipped))


def _snap_uniform(
    profile: np.ndarray,
    limit: int,
    target_step: float,
    cfg: dict,
    min_required: int,
) -> list[int]:
    """Place cuts at uniform intervals, snapping each to a nearby gradient peak."""
    if limit == 0:
        return [0]
    if limit == 1:
        return [0, 1]

    if np.isfinite(target_step) and target_step > 0.0:
        desired = int(round(limit / target_step))
    else:
        desired = 0
    desired = min(max(desired, max(min_required - 1, 1)), limit)

    cell_w = limit / desired
    window = max(cell_w * cfg["walker_search_window_ratio"], cfg["walker_min_search_window"])
    mean_val = float(profile.mean()) if len(profile) else 0.0
    threshold = mean_val * cfg["walker_strength_threshold"]

    cuts = [0]
    for idx in range(1, desired):
        target = cell_w * idx
        prev = cuts[-1]
        if prev + 1 >= limit:
            break
        start = max(int(np.floor(target - window)), prev + 1, 0)
        end = min(int(np.ceil(target + window)), limit - 1)
        if end < start:
            start = end = prev + 1

        plen = len(profile)
        if plen == 0:
            best_idx = min(start, 0)
            best_val = -1.0
        else:
            s = min(start, plen - 1)
            e = min(end, plen - 1)
            sub = profile[s:e + 1]
            best_idx = s + int(np.argmax(sub))
            best_val = float(sub.max())

        if best_val < threshold:
            fb = int(round(target))
            if fb <= prev:
                fb = prev + 1
            if fb >= limit:
                fb = max(limit - 1, prev + 1)
            best_idx = fb
        cuts.append(best_idx)

    if cuts[-1] != limit:
        cuts.append(limit)
    return _sanitize_cuts(cuts, limit)


# ── Resample (mode per cell) ──────────────────────────────────────

def _resample(arr: np.ndarray, cols: list[int], rows: list[int]) -> np.ndarray:
    if len(cols) < 2 or len(rows) < 2:
        raise ValueError("insufficient grid cuts for resampling")
    out_h = len(rows) - 1
    out_w = len(cols) - 1
    out = np.zeros((out_h, out_w, 4), dtype=np.uint8)

    for yi in range(out_h):
        ys, ye = rows[yi], rows[yi + 1]
        if ye <= ys:
            continue
        for xi in range(out_w):
            xs, xe = cols[xi], cols[xi + 1]
            if xe <= xs:
                continue
            cell = arr[ys:ye, xs:xe]
            # Pack RGBA into uint32 with R in high byte so lexicographic
            # tie-break matches the Rust [u8;4] comparison (r, g, b, a).
            packed = (
                (cell[:, :, 0].astype(np.uint32) << 24)
                | (cell[:, :, 1].astype(np.uint32) << 16)
                | (cell[:, :, 2].astype(np.uint32) << 8)
                | cell[:, :, 3].astype(np.uint32)
            ).ravel()
            unique, counts = np.unique(packed, return_counts=True)
            # Sort by count desc, then packed asc for deterministic ties.
            order = np.lexsort((unique, -counts))
            w = int(unique[order[0]])
            out[yi, xi] = [
                (w >> 24) & 0xFF,
                (w >> 16) & 0xFF,
                (w >> 8) & 0xFF,
                w & 0xFF,
            ]
    return out
