"""generate_asset() — the public API tying Phases 1-5 together.

Signature:

    generate_asset(category, prompt, asset_id, settings?, metadata?,
                   backend?, force=False) -> AssetRecord

Flow:
  1. Look up CategoryConfig; merge settings over its defaults.
  2. Validate metadata against the category's metadata_schema.
  3. Pick the backend (explicit arg > category default + fallback).
  4. Compute cache_key. If hit + not force, return cached AssetRecord.
  5. On miss: generate N variations via backend, score each, keep best.
  6. Run the post_process chain on the best image.
  7. Write cache entry + update by_id pointer.

Errors surfaced (for the engine validator + error_fixer mapping):
  unknown_category           — category not in CATEGORIES
  metadata_schema_violation  — metadata fails validate_metadata
  chain_fan_out_invalid      — post_process chain bad (caught by run_chain)
  unknown_op                 — post_process references missing op
  backend_unavailable_no_fallback — primary backend down + no fallback

score_warning is warn-only — doesn't raise. Author must triage via
sidecar JSON / build log.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from sprite_backends import Backend, BackendName, get_backend
from sprite_cache import (
    AssetRecord,
    cache_key as _cache_key,
    cache_lookup,
    cache_write,
    update_by_id,
)
from sprite_categories import (
    CATEGORIES,
    CategoryConfig,
    MetadataSchemaViolation,
    validate_metadata,
)
from sprite_ops import (
    ChainFanOutInvalid,
    PipelineContext,
    run_chain,
)
from sprite_scorers import score as _score


class BackendUnavailableNoFallback(RuntimeError):
    """Raised when the preferred backend fails health-probe and no
    `backend_fallback` is configured. Maps to the
    `backend_unavailable_no_fallback` validator error."""


class UnknownCategory(KeyError):
    """Raised when `category` isn't in CATEGORIES. Maps to
    `unknown_category`."""


# ─── Public API ──────────────────────────────────────────────────────

def generate_asset(
    category: str,
    prompt: str,
    asset_id: str,
    settings: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
    backend: Optional[Backend] = None,
    force: bool = False,
) -> AssetRecord:
    settings = dict(settings or {})
    metadata = dict(metadata or {})

    cfg = _resolve_category(category)
    validate_metadata(category, metadata)

    backend = _resolve_backend(cfg, explicit=backend)
    merged_settings = _merge_settings(cfg, settings)
    seed = merged_settings.get("seed")

    # Cache key uses the category defaults for default-stripping so
    # (settings={}) and (settings={variations: cfg.variations}) collide.
    key = _cache_key(
        category=category,
        prompt=prompt,
        settings=merged_settings,
        backend_version=backend.version,
        seed=seed,
        category_defaults=_cfg_defaults(cfg),
    )

    if not force:
        hit = cache_lookup(key)
        if hit is not None:
            # Cache hit carries its own persisted metadata; we still
            # stamp the requested asset_id + current by_id pointer.
            hit.asset_id = asset_id
            update_by_id(category, asset_id, key)
            return hit

    # Miss → generate N variations, pick best, run chain.
    image, score_val, per_metric = _generate_best(
        backend, cfg, prompt, merged_settings, metadata, seed,
    )

    ctx = PipelineContext(
        category=category,
        asset_id=asset_id,
        metadata=metadata,
        target_size=cfg.target_size,
        palette_colors=cfg.palette_colors,
    )
    chain_result = run_chain(image, cfg.post_process, ctx)
    if isinstance(chain_result.output, list):
        # A chain ending mid-fan-out is invalid; validate_chain should
        # have caught it already, but guard at runtime anyway.
        raise ChainFanOutInvalid(
            f"post_process ended in a list (missing collector?): "
            f"{cfg.post_process}"
        )
    final_img: Image.Image = chain_result.output  # type: ignore[assignment]

    score_warning = (
        cfg.min_acceptable_score is not None
        and score_val < cfg.min_acceptable_score
    )

    merged_metadata = {
        **metadata,
        **chain_result.metadata_updates,
    }
    if chain_result.atlas is not None:
        merged_metadata["atlas"] = chain_result.atlas

    rec = AssetRecord(
        hash=key,
        category=category,
        asset_id=asset_id,
        prompt=prompt,
        settings=merged_settings,
        metadata=merged_metadata,
        image_path=Path(),  # filled by cache_write
        cache_hit=False,
        score=round(score_val, 4),
        score_warning=score_warning,
        backend_used=backend.version,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    cache_write(key, rec, final_img)
    update_by_id(category, asset_id, key)
    return rec


# ─── Helpers ─────────────────────────────────────────────────────────

def _resolve_category(name: str) -> CategoryConfig:
    cfg = CATEGORIES.get(name)
    if cfg is None:
        raise UnknownCategory(
            f"unknown_category: {name!r} not in CATEGORIES "
            f"({sorted(CATEGORIES.keys())})"
        )
    return cfg


def _resolve_backend(
    cfg: CategoryConfig,
    explicit: Optional[Backend],
) -> Backend:
    """Explicit arg wins. Otherwise try cfg.backend; if unavailable
    and a fallback is configured, probe that. If neither is live, raise
    BackendUnavailableNoFallback."""
    if explicit is not None:
        return explicit

    primary = get_backend(cfg.backend)
    if primary.available():
        return primary
    if cfg.backend_fallback is None:
        raise BackendUnavailableNoFallback(
            f"preferred backend {cfg.backend!r} unavailable and no "
            f"backend_fallback configured for category {cfg.name!r}"
        )
    fb = get_backend(cfg.backend_fallback)
    if fb.available():
        print(f"[generate_asset] {cfg.name}: {cfg.backend} down, "
              f"using fallback {cfg.backend_fallback}")
        return fb
    raise BackendUnavailableNoFallback(
        f"both primary ({cfg.backend}) and fallback "
        f"({cfg.backend_fallback}) unavailable for {cfg.name!r}"
    )


def _cfg_defaults(cfg: CategoryConfig) -> dict[str, Any]:
    """The knobs the cache's default-strip consults. Not all
    CategoryConfig fields are generation-time — only the ones that
    influence backend output."""
    return {
        "variations": cfg.variations,
        "gen_width": cfg.gen_size[0],
        "gen_height": cfg.gen_size[1],
        "target_width": cfg.target_size[0],
        "target_height": cfg.target_size[1],
        "palette_colors": cfg.palette_colors,
    }


def _merge_settings(
    cfg: CategoryConfig,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Overlay caller settings on top of category defaults. Caller
    supplies any of: variations, gen_width, gen_height, target_width,
    target_height, palette_colors, seed, steps, guidance."""
    base = _cfg_defaults(cfg)
    out = {**base}
    for k, v in settings.items():
        if v is not None:
            out[k] = v
    # Seed: if missing, leave absent (cache_key will normalize).
    if "seed" in settings:
        out["seed"] = settings["seed"]
    return out


def _derive_variation_seed(base: Optional[int], i: int) -> int:
    """Derive a per-variation seed from the base. If base is None we
    generate a fresh random seed so each variation is distinct."""
    if base is None:
        return random.randint(0, 2**31 - 1) ^ (i * 7919)
    return int(base) ^ (i * 7919)


def _generate_best(
    backend: Backend,
    cfg: CategoryConfig,
    prompt: str,
    settings: dict[str, Any],
    metadata: dict[str, Any],
    seed: Optional[int],
) -> tuple[Image.Image, float, dict[str, float]]:
    """Generate N variations, score each, return the top-scoring one.
    Prompt gets category.style_prefix + (style_suffix may be empty)."""
    variations = int(settings.get("variations", cfg.variations))
    gw = int(settings.get("gen_width", cfg.gen_size[0]))
    gh = int(settings.get("gen_height", cfg.gen_size[1]))
    steps = settings.get("steps")
    guidance = settings.get("guidance")

    styled = cfg.style_prefix + prompt + cfg.style_suffix
    neg = cfg.negative_prompt or None

    candidates: list[tuple[Image.Image, float, dict[str, float]]] = []
    for i in range(variations):
        s = _derive_variation_seed(seed, i)
        img = backend.generate(
            styled, width=gw, height=gh,
            steps=steps, guidance=guidance,
            seed=s, negative_prompt=neg,
        )
        score_val, per_metric = _score(img, cfg.scorer, metadata)
        candidates.append((img, score_val, per_metric))

    # max-by-score; ties broken by insertion order (earliest wins).
    best = max(candidates, key=lambda c: c[1])
    return best
