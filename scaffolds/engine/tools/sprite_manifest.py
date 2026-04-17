"""AssetManifest loader + validator.

Manifest shape (scaffolds/<game>/assets.manifest.json):

    {
      "schema_version": "1",
      "backend": "ernie@turbo-8s",             # optional — build-time hint
      "assets": [
        {
          "id": "player_knight",
          "category": "character",
          "prompt": "pixel art knight with sword, side view",
          "metadata": { "class": "knight", "facing": "side" },
          "settings": null                      # optional overrides
        },
        ...
      ]
    }

Runtime manifest (public/sprites/manifest.json) is emitted by
build_sprites — its shape is a flat `id → entry` map for the loader.
This module owns the authoring-side shape only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


SUPPORTED_MANIFEST_VERSIONS = {"1"}


class UnsupportedManifestVersion(ValueError):
    """Maps to validator error `unsupported_manifest_version`."""


@dataclass
class AssetSpec:
    id: str
    category: str
    prompt: str
    metadata: dict[str, Any] = field(default_factory=dict)
    settings: Optional[dict[str, Any]] = None


@dataclass
class AssetManifest:
    schema_version: str
    backend: Optional[str]
    assets: list[AssetSpec]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AssetManifest":
        ver = str(raw.get("schema_version", "0"))
        if ver not in SUPPORTED_MANIFEST_VERSIONS:
            raise UnsupportedManifestVersion(
                f"unsupported_manifest_version: schema_version={ver!r} "
                f"not in {sorted(SUPPORTED_MANIFEST_VERSIONS)}"
            )
        assets_raw = raw.get("assets") or []
        assets: list[AssetSpec] = []
        for i, a in enumerate(assets_raw):
            if not isinstance(a, dict):
                raise ValueError(f"assets[{i}] must be an object, got {type(a).__name__}")
            aid = a.get("id")
            cat = a.get("category")
            prompt = a.get("prompt")
            if not aid or not cat or not prompt:
                raise ValueError(
                    f"assets[{i}] missing required id/category/prompt: {a!r}"
                )
            assets.append(AssetSpec(
                id=str(aid),
                category=str(cat),
                prompt=str(prompt),
                metadata=dict(a.get("metadata") or {}),
                settings=a.get("settings") or None,
            ))
        return cls(
            schema_version=ver,
            backend=raw.get("backend"),
            assets=assets,
        )


def load_manifest(path: Path) -> AssetManifest:
    raw = json.loads(Path(path).read_text())
    return AssetManifest.from_dict(raw)
