#!/usr/bin/env python3
"""build_sprites — scaffold build step.

Reads `assets.manifest.json` from a project dir, runs each asset
through `generate_asset()`, copies the cached PNG into
`public/sprites/<id>.png`, and emits a flat runtime manifest at
`public/sprites/manifest.json` that `src/sprites/loader.ts` fetches.

Usage:
    python build_sprites.py <project_dir>

Exit code 0 = build clean. Non-zero = at least one asset failed
validation (unknown category / bad metadata / backend down). A
score_warning is NOT a failure — it's logged but build continues.

Tileset assets additionally emit `<id>.atlas.json` alongside the PNG
— the atlas dict that pack_spritesheet wrote onto AssetRecord.metadata.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from generate_asset import (
    generate_asset,
    BackendUnavailableNoFallback,
    UnknownCategory,
)
from sprite_categories import MetadataSchemaViolation
from sprite_manifest import (
    AssetManifest,
    UnsupportedManifestVersion,
    load_manifest,
)
from sprite_ops import ChainFanOutInvalid


@dataclass
class BuildResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    cache_hits: int = 0
    score_warnings: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    manifest_path: Path = field(default_factory=Path)


# ─── Error mapping to validator kinds ────────────────────────────────

def _classify_error(e: Exception) -> str:
    if isinstance(e, UnknownCategory):
        return "unknown_category"
    if isinstance(e, MetadataSchemaViolation):
        return "metadata_schema_violation"
    if isinstance(e, ChainFanOutInvalid):
        return "chain_fan_out_invalid"
    if isinstance(e, BackendUnavailableNoFallback):
        return "backend_unavailable_no_fallback"
    if isinstance(e, UnsupportedManifestVersion):
        return "unsupported_manifest_version"
    return e.__class__.__name__


# ─── Build step ──────────────────────────────────────────────────────

def build_sprites(project_dir: Path,
                  manifest_filename: str = "assets.manifest.json",
                  out_subdir: str = "public/sprites") -> BuildResult:
    project_dir = Path(project_dir).resolve()
    manifest_path = project_dir / manifest_filename
    out_dir = project_dir / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        manifest: AssetManifest = load_manifest(manifest_path)
    except UnsupportedManifestVersion as e:
        return BuildResult(errors=[{
            "asset_id": None,
            "kind": "unsupported_manifest_version",
            "message": str(e),
        }])

    result = BuildResult(manifest_path=manifest_path)
    runtime_assets: dict[str, dict[str, Any]] = {}

    for asset in manifest.assets:
        try:
            rec = generate_asset(
                category=asset.category,
                prompt=asset.prompt,
                asset_id=asset.id,
                settings=asset.settings,
                metadata=asset.metadata,
            )
        except Exception as e:
            result.errors.append({
                "asset_id": asset.id,
                "kind": _classify_error(e),
                "message": str(e),
            })
            print(f"[build_sprites] ✗ {asset.id}: {_classify_error(e)} — {e}")
            continue

        # Copy the cached PNG into public/sprites/<id>.png.
        dest_png = out_dir / f"{asset.id}.png"
        shutil.copyfile(rec.image_path, dest_png)

        entry: dict[str, Any] = {
            "id": asset.id,
            "path": f"{out_subdir.replace('public/', '')}/{asset.id}.png",
            "category": asset.category,
            "metadata": rec.metadata,
        }

        # Tileset: write the atlas JSON sidecar.
        atlas = rec.metadata.get("atlas")
        if atlas is not None:
            atlas_path = out_dir / f"{asset.id}.atlas.json"
            # Rewrite the atlas' sheet filename so it references the
            # public path, not cache-internal names.
            out_atlas = {**atlas, "sheet": f"{asset.id}.png"}
            atlas_path.write_text(json.dumps(out_atlas, indent=2))
            entry["metadata"]["atlas"] = (
                f"{out_subdir.replace('public/', '')}/{asset.id}.atlas.json"
            )

        runtime_assets[asset.id] = entry
        result.records.append(entry)
        if rec.cache_hit:
            result.cache_hits += 1
        if rec.score_warning:
            result.score_warnings += 1
            print(f"[build_sprites] ⚠ {asset.id}: score "
                  f"{rec.score:.3f} below min_acceptable — carrying on")
        else:
            print(f"[build_sprites] {'•' if rec.cache_hit else '✓'} "
                  f"{asset.id} (score={rec.score:.3f}"
                  f"{', cached' if rec.cache_hit else ''})")

    # Runtime manifest — consumed by loader.ts.
    runtime_path = out_dir / "manifest.json"
    runtime_path.write_text(json.dumps({
        "schema_version": "1",
        "assets": runtime_assets,
    }, indent=2))

    n = len(manifest.assets)
    ok = n - len(result.errors)
    print(f"[build_sprites] summary: {ok}/{n} assets, "
          f"{result.cache_hits} cache hits, "
          f"{result.score_warnings} warnings, "
          f"{len(result.errors)} errors → {runtime_path}")
    return result


# ─── CLI ─────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("project_dir", type=Path,
                   help="project root (must contain assets.manifest.json)")
    p.add_argument("--manifest", default="assets.manifest.json",
                   help="manifest filename (default: assets.manifest.json)")
    p.add_argument("--out", default="public/sprites",
                   help="output subdir (default: public/sprites)")
    args = p.parse_args(argv)

    result = build_sprites(args.project_dir,
                           manifest_filename=args.manifest,
                           out_subdir=args.out)
    return 0 if not result.errors else 2


if __name__ == "__main__":
    sys.exit(main())
