"""Named scorer registry — weighted sums over sprite_metrics.

A scorer picks the metrics relevant to its sprite category and their
relative weights (summing ~1.0). score() dispatches to the metric
registry in sprite_metrics.py and returns (final_score, per_metric_dict).

9 scorers in v1.1 (default_scorer is the catch-all). Weights come
from recipes/<category>.md's scorer section + recipes' note_001.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from PIL import Image

from sprite_metrics import compute_metric


@dataclass
class ScorerSpec:
    name: str
    weights: dict[str, float]  # metric_name → weight; should sum to ~1.0


SCORERS: dict[str, ScorerSpec] = {
    # Coarse default — used when a category doesn't pick something
    # specific. Matches the original sprite_pipeline.score_sprite
    # behaviour (4 equal-weight metrics).
    "default_scorer": ScorerSpec("default_scorer", {
        "coverage":        0.25,
        "centering":       0.25,
        "fragmentation":   0.25,
        "color_diversity": 0.25,
    }),

    # Per-category tunings.
    "character_scorer": ScorerSpec("character_scorer", {
        "coverage":        0.20,
        "centering":       0.25,
        "fragmentation":   0.30,  # characters want 1 blob
        "color_diversity": 0.15,
        "silhouette":      0.10,
    }),
    "item_scorer": ScorerSpec("item_scorer", {
        "coverage":        0.30,
        "centering":       0.30,
        "fragmentation":   0.20,
        "color_diversity": 0.20,
    }),
    "texture_scorer": ScorerSpec("texture_scorer", {
        "coverage":        0.40,
        "color_diversity": 0.30,
        "tileability":     0.30,
    }),
    "tileset_scorer": ScorerSpec("tileset_scorer", {
        "tile_count":         0.25,
        "palette_coherence":  0.20,
        "seamlessness":       0.25,
        "per_tile_coverage":  0.15,
        "edge_fringe":        0.15,
    }),
    "background_scorer": ScorerSpec("background_scorer", {
        "aspect_fidelity":      0.10,
        "seamless_horizontal":  0.35,
        "no_dominant_subject":  0.20,
        "opacity":              0.20,
        "color_diversity":      0.15,
    }),
    "ui_element_scorer": ScorerSpec("ui_element_scorer", {
        "flatness":       0.35,
        "contrast":       0.25,
        "clean_edges":    0.20,
        "centering":      0.10,
        "opacity":        0.10,
    }),
    "effect_scorer": ScorerSpec("effect_scorer", {
        "radial_coherence":     0.30,
        "brightness_range":     0.25,
        "color_warmth":         0.15,
        "coverage":             0.15,
        "no_unwanted_subject":  0.15,
    }),
    "portrait_scorer": ScorerSpec("portrait_scorer", {
        "eye_detection":     0.30,
        "head_proportion":   0.20,
        "centering":         0.15,
        "palette_coherence": 0.15,
        "no_text":           0.10,
        "clean_silhouette":  0.10,
    }),
}


def score(
    img: Image.Image,
    scorer_name: str = "default_scorer",
    metadata: Optional[dict[str, Any]] = None,
) -> tuple[float, dict[str, float]]:
    """Compute a weighted score. Returns (final, per_metric). Unknown
    scorer names fall back to default_scorer rather than raising — the
    generation pipeline should never be stuck on a scorer typo."""
    spec = SCORERS.get(scorer_name) or SCORERS["default_scorer"]
    per_metric: dict[str, float] = {}
    total = 0.0
    weight_sum = 0.0
    for metric, w in spec.weights.items():
        v = compute_metric(metric, img, metadata)
        per_metric[metric] = round(v, 4)
        total += v * w
        weight_sum += w
    if weight_sum > 0:
        final = total / weight_sum
    else:
        final = 0.0
    per_metric["_final"] = round(final, 4)
    per_metric["_scorer"] = scorer_name  # type: ignore[assignment]
    return float(final), per_metric
