#!/usr/bin/env python3
"""sprite pipeline E2E — Phase 10 ship-gate.

Runs the 5-asset START_HERE.md fixture through build_sprites.py against
a StubBackend (so this test is hermetic and doesn't depend on the live
:8090 image endpoint). Confirms:

  - 5 assets build clean
  - No validator errors
  - public/sprites/ ends up with 5 PNGs + manifest.json + atlas.json
  - Runtime manifest schema is correct
  - Second build is 5/5 cache hits (content-addressable cache works)
  - Tileset produces atlas.json with 16 tiles

Live-image E2E awaits tsunami server-side wiring of /v1/images/generate
(OpenAPI advertises the route but the current deployment returns 404).
When the live backend comes online, drop the `--stub` flag.

Usage:
    python3 scaffolds/engine/tests/sprite_e2e.py            # hermetic, default
    python3 scaffolds/engine/tests/sprite_e2e.py --live     # live gen (needs :8090 image route)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scaffolds" / "engine" / "tools"))


FIXTURE = {
    "schema_version": "1",
    "backend": "zimage@turbo-9s",
    "assets": [
        {"id": "player_hero", "category": "character",
         "prompt": "pixel art hero with sword, side view, green tunic",
         "metadata": {"class": "hero", "facing": "side"}},
        {"id": "slime_green", "category": "character",
         "prompt": "pixel art green slime monster, cute, drippy",
         "metadata": {"class": "slime"}},
        {"id": "coin_gold", "category": "item",
         "prompt": "pixel art gold coin, shiny, round",
         "metadata": {"rarity": "common"}},
        {"id": "grass_tiles", "category": "tileset",
         "prompt": "pixel art grass tiles, 4x4 grid, overworld, top-down",
         "metadata": {"biome": "overworld",
                      "tile_grid_w": 4, "tile_grid_h": 4}},
        {"id": "sky_bg", "category": "background",
         "prompt": "pixel art cloudy sky, horizontal parallax layer",
         "metadata": {"layer": "far", "tileable_horizontal": True}},
    ],
}


def _install_stub_backend() -> None:
    """Monkey-patch generate_asset._resolve_backend to return a
    deterministic stub backend. Produces plausible sprites without
    touching the network."""
    import generate_asset  # noqa
    from sprite_backends import Backend

    class StubBackend(Backend):
        name = "z_image"
        version = "stub-test"
        endpoint = ""
        default_steps = 9
        default_guidance = 0.0

        def generate(self, prompt, width, height, steps=None,
                     guidance=None, seed=None, negative_prompt=None):
            rng = np.random.default_rng(seed or 42)
            arr = np.zeros((height, width, 4), dtype=np.uint8)
            # Magenta bg at edges, opaque blob at center.
            arr[:, :, 0] = 255
            arr[:, :, 2] = 255
            arr[:, :, 3] = 255
            cy, cx = height // 2, width // 2
            r = int(min(height, width) * 0.35)
            arr[cy - r:cy + r, cx - r:cx + r, :3] = rng.integers(
                40, 220, (2 * r, 2 * r, 3), dtype=np.uint8,
            )
            return Image.fromarray(arr)

        def available(self) -> bool: return True

    stub = StubBackend()
    generate_asset._resolve_backend = lambda cfg, explicit=None: stub


def run_build(project_dir: Path, live: bool) -> dict:
    if not live:
        _install_stub_backend()
    from build_sprites import build_sprites
    return build_sprites(project_dir)


def assert_ship_gate(project_dir: Path, result, fixture: dict) -> None:
    out = project_dir / "public" / "sprites"
    expected_ids = [a["id"] for a in fixture["assets"]]

    # Gate 12.1: build clean (no errors).
    assert not result.errors, f"errors: {result.errors}"
    assert len(result.records) == len(expected_ids), \
        f"records {len(result.records)} != {len(expected_ids)}"

    # Gate 12.2: every PNG lands + runtime manifest exists.
    for aid in expected_ids:
        assert (out / f"{aid}.png").exists(), f"missing {aid}.png"
    rt_path = out / "manifest.json"
    assert rt_path.exists(), "runtime manifest missing"
    rt = json.loads(rt_path.read_text())
    assert rt["schema_version"] == "1", rt
    assert set(rt["assets"].keys()) == set(expected_ids)
    for aid, entry in rt["assets"].items():
        assert entry["path"].endswith(f"{aid}.png"), entry
        assert entry["category"] in {"character", "item", "tileset",
                                     "background", "ui_element",
                                     "effect", "portrait", "texture"}

    # Gate 12.3: tileset atlas JSON present + well-formed.
    atlas_path = out / "grass_tiles.atlas.json"
    assert atlas_path.exists(), "tileset atlas JSON missing"
    atlas = json.loads(atlas_path.read_text())
    assert atlas["schema_version"] == "1"
    assert atlas["tile_count"] == 16, atlas["tile_count"]
    assert len(atlas["tiles"]) == 16
    assert atlas["sheet"] == "grass_tiles.png"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--live", action="store_true",
                        help="use real backend instead of stub (needs :8090 image route)")
    parser.add_argument("--out",
                        help="pre-existing project dir; default = tempdir")
    parser.add_argument("--keep", action="store_true",
                        help="don't delete tempdir on exit (artefact inspection)")
    args = parser.parse_args(argv)

    td = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="sprite_e2e_"))
    td.mkdir(parents=True, exist_ok=True)
    (td / "assets.manifest.json").write_text(json.dumps(FIXTURE, indent=2))

    # Clean cache so cold-build + rebuild-hit counts are honest.
    from sprite_cache import _clear_cache as clear_cache
    clear_cache()

    print(f"[e2e] cold build → {td}")
    cold = run_build(td, args.live)
    assert_ship_gate(td, cold, FIXTURE)
    print(f"[e2e] cold: {len(cold.records)}/{len(FIXTURE['assets'])} "
          f"records, {cold.cache_hits} hits, {len(cold.errors)} errors")

    print(f"[e2e] warm rebuild →")
    warm = run_build(td, args.live)
    assert_ship_gate(td, warm, FIXTURE)
    assert warm.cache_hits == len(FIXTURE["assets"]), \
        f"warm rebuild hits {warm.cache_hits} != 5"
    print(f"[e2e] warm: {warm.cache_hits}/{len(warm.records)} cache hits")

    print("[e2e] SHIP GATE #12 (end-to-end): ✓ GREEN")
    if not args.keep:
        shutil.rmtree(td)
    else:
        print(f"[e2e] artefacts left at {td}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
