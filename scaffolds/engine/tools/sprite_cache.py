"""Content-addressable cache for generated sprites.

Keyed on (category, normalized prompt, normalized settings,
backend_version, seed) → sha256[:16] hex. Two indexes:

    sprite_cache/
        by_hash/<ab>/<abcd1234ef567890>.png   + .json sidecar
        by_id/<category>/<asset_id>/
            current        → {"hash": "...", "generated_at": "..."}
            history.json   → list of past hashes (append-only)

Lookup semantics:

    cache_lookup(key) -> AssetRecord | None   # None == miss
    cache_write(key, record, img) -> Path     # writes both blob + sidecar,
                                              # returns blob path
    update_by_id(cat, asset_id, key)          # update by_id pointer
                                              # appending to history
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image

# ─── Paths ───────────────────────────────────────────────────────────
#
# CACHE_ROOT is anchored on ark/ workspace/ so cache survives process
# restarts without polluting the repo. Per G4 in START_HERE.md we
# mkdir -p on import so the first generate_asset call doesn't trip on
# missing directories.

CACHE_ROOT = (Path(__file__).resolve().parents[3]
              / "workspace" / "sprite_cache")
BY_HASH = CACHE_ROOT / "by_hash"
BY_ID = CACHE_ROOT / "by_id"

BY_HASH.mkdir(parents=True, exist_ok=True)
BY_ID.mkdir(parents=True, exist_ok=True)


# ─── AssetRecord shape ───────────────────────────────────────────────
#
# Carried end-to-end: cache_write persists it; generate_asset returns
# it; build_sprites reads it. The same fields stamp into the
# per-asset sidecar JSON so we can reconstruct a record from disk
# without touching the cache-by-id pointer.

@dataclass
class AssetRecord:
    hash: str
    category: str
    asset_id: str
    prompt: str
    settings: dict[str, Any]
    metadata: dict[str, Any]
    image_path: Path
    cache_hit: bool = False
    score: float = 0.0
    score_warning: bool = False
    backend_used: str = ""
    generated_at: str = ""

    def to_sidecar(self) -> dict[str, Any]:
        """Shape written to <hash>.json. `image_path` is stored
        relative to CACHE_ROOT so the cache is relocatable."""
        d = asdict(self)
        d["image_path"] = str(Path(d["image_path"]).relative_to(CACHE_ROOT))
        return d

    @classmethod
    def from_sidecar(cls, data: dict[str, Any]) -> "AssetRecord":
        data = {**data, "image_path": CACHE_ROOT / data["image_path"]}
        return cls(**data)


# ─── Settings normalization ──────────────────────────────────────────
#
# Two sprite requests with equivalent intent must hash the same —
# {variations: 4} and {} should collide when 4 is the category's
# default. The normalizer:
#   1. drops None values
#   2. sorts keys via json.dumps(sort_keys=True) at key-compute time
#   3. strips category defaults when a defaults dict is supplied
#
# Defaults-stripping is opt-in — generate_asset knows the category
# config, cache_key doesn't. The caller passes `category_defaults`.

def _normalize_settings(
    settings: dict[str, Any],
    category_defaults: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    defaults = category_defaults or {}
    out: dict[str, Any] = {}
    for k, v in settings.items():
        if v is None:
            # Keep only the `seed: None` case — explicit None for seed
            # means "deterministic key without a seed," not "default
            # seed." All other None fields drop.
            if k == "seed":
                out[k] = None
            continue
        if k in defaults and defaults[k] == v:
            continue
        out[k] = v
    return out


# ─── Key compute ─────────────────────────────────────────────────────

def cache_key(
    category: str,
    prompt: str,
    settings: dict[str, Any],
    backend_version: str,
    seed: Optional[int] = None,
    category_defaults: Optional[dict[str, Any]] = None,
) -> str:
    """Compute the content-addressable cache key.

    Stable under dict-key reordering, None-vs-missing (for non-seed
    fields), and under category-default stripping. Not stable under
    prompt whitespace/casing — we lower + strip to paper over minor
    authoring drift."""
    # Always stamp seed into the payload — missing vs explicit None
    # must collide (spec: "Seed: if missing, set to None explicitly,
    # don't collapse with 0"). The explicit `seed` kwarg wins over
    # settings["seed"] when both appear.
    eff_settings = {**settings}
    if seed is not None:
        eff_settings["seed"] = seed
    elif "seed" not in eff_settings:
        eff_settings["seed"] = None
    eff = _normalize_settings(eff_settings, category_defaults)

    payload = {
        "category": category,
        "prompt": prompt.strip().lower(),
        "settings": eff,
        "backend": backend_version,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ─── Lookup + write ──────────────────────────────────────────────────

def _hash_bucket(key: str) -> Path:
    return BY_HASH / key[:2]


def _hash_paths(key: str) -> tuple[Path, Path]:
    bucket = _hash_bucket(key)
    return bucket / f"{key}.png", bucket / f"{key}.json"


def cache_lookup(key: str) -> Optional[AssetRecord]:
    """Return the record if the cache has both blob + sidecar for this
    key. Missing or partial entries count as a miss — partial means a
    prior write crashed and the blob is untrusted."""
    blob, sidecar = _hash_paths(key)
    if not blob.exists() or not sidecar.exists():
        return None
    try:
        data = json.loads(sidecar.read_text())
    except Exception:
        return None
    rec = AssetRecord.from_sidecar(data)
    rec.cache_hit = True
    return rec


def cache_write(
    key: str,
    record: AssetRecord,
    image: Image.Image,
) -> Path:
    """Persist image + sidecar under by_hash/. Returns the blob path
    so generate_asset can stamp it onto the record it returns."""
    blob, sidecar = _hash_paths(key)
    blob.parent.mkdir(parents=True, exist_ok=True)
    # PIL's .save handles PNG encoding; we leave the caller to decide
    # pixel-size (usually target_size after the post-process chain).
    image.save(blob)

    record.hash = key
    record.image_path = blob
    if not record.generated_at:
        record.generated_at = datetime.now(timezone.utc).isoformat()
    sidecar.write_text(json.dumps(record.to_sidecar(), indent=2,
                                  default=str))
    return blob


# ─── by_id pointer (asset_id → current hash) ─────────────────────────

def _by_id_dir(category: str, asset_id: str) -> Path:
    return BY_ID / category / asset_id


def update_by_id(category: str, asset_id: str, key: str) -> None:
    """Stamp the by_id pointer + append to history. History is a
    dedupe-aware append: if `key` is already the tail, we skip rather
    than add a duplicate row (cache-hit calls otherwise bloat it)."""
    d = _by_id_dir(category, asset_id)
    d.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    current = d / "current"
    history = d / "history.json"

    current.write_text(json.dumps({"hash": key, "generated_at": now}, indent=2))

    entries: list[dict] = []
    if history.exists():
        try:
            entries = json.loads(history.read_text())
        except Exception:
            entries = []
    if not entries or entries[-1].get("hash") != key:
        entries.append({"hash": key, "generated_at": now})
        history.write_text(json.dumps(entries, indent=2))


def current_by_id(category: str, asset_id: str) -> Optional[str]:
    """Return the hash currently pointed to by the by_id entry, or
    None if we've never generated this asset_id under this category."""
    current = _by_id_dir(category, asset_id) / "current"
    if not current.exists():
        return None
    try:
        return json.loads(current.read_text()).get("hash")
    except Exception:
        return None


# ─── Utilities for tests / maintenance ───────────────────────────────

def _clear_cache() -> None:
    """Wipe the cache — tests use this to start from a known state."""
    for d in (BY_HASH, BY_ID):
        if d.exists():
            shutil.rmtree(d)
    BY_HASH.mkdir(parents=True, exist_ok=True)
    BY_ID.mkdir(parents=True, exist_ok=True)
