#!/usr/bin/env python3
"""
Game from text — generate a playable RPG level from a single sentence.

Pipeline:
  1. Text → tilemap_gen.py → map JSON
  2. Map JSON → detect needed sprites → sprite_pipeline.py batch
  3. Output: map JSON + sprite assets → load in RPG

Usage:
  python game_from_text.py "haunted graveyard with skeletons and a necromancer boss"
  python game_from_text.py "peaceful fishing village by the sea with a merchant"
  python game_from_text.py --no-sprites "dark cave with spiders"  # skip sprite gen
"""

import argparse
import json
from pathlib import Path

from tilemap_gen import generate_tilemap, NPC_TEMPLATES

OUTPUT_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "webgpu-game" / "public"


def get_needed_sprites(tilemap: dict) -> list[dict]:
    """Analyze a tilemap and return sprite generation jobs for missing assets."""
    needed = []
    sprite_dir = OUTPUT_DIR / "sprites"

    # Check NPCs
    for npc in tilemap.get('npcs', []):
        sprite = npc.get('sprite', '')
        best_path = sprite_dir / "character" / sprite / f"{sprite}_best.png"
        if not best_path.exists():
            tmpl = NPC_TEMPLATES.get(sprite.replace('rpg_', '').replace('npc_', ''), {})
            needed.append({
                "name": sprite,
                "category": "character",
                "prompt": f"{npc.get('name', sprite)}, pixel art game character, standing",
                "variations": 4,
                "target_size": [64, 64] if not npc.get('hostile') else [48, 48],
                "colors": 12,
            })

    # Check tiles (textures)
    seen_tiles = set()
    for row in tilemap.get('layers', {}).get('ground', []):
        for tile in row:
            seen_tiles.add(tile)

    for tile in seen_tiles:
        best_path = sprite_dir / "texture" / f"tile_{tile}" / f"tile_{tile}_best.png"
        if not best_path.exists():
            needed.append({
                "name": f"tile_{tile}",
                "category": "texture",
                "prompt": f"{tile} terrain, top down view, pixel art game tile",
                "variations": 3,
                "target_size": [32, 32],
                "colors": 8,
            })

    # Check props
    seen_props = set()
    for prop in tilemap.get('props', []):
        seen_props.add(prop.get('type', ''))

    for prop_type in seen_props:
        best_path = sprite_dir / "object" / prop_type / f"{prop_type}_best.png"
        if not best_path.exists():
            needed.append({
                "name": prop_type,
                "category": "object",
                "prompt": f"{prop_type.replace('prop_', '')} game prop, pixel art, top down",
                "variations": 4,
                "target_size": [48, 48],
                "colors": 10,
            })

    return needed


def main():
    parser = argparse.ArgumentParser(description="Generate a playable RPG level from text")
    parser.add_argument("description", help="Text description of the level")
    parser.add_argument("--width", type=int, default=24)
    parser.add_argument("--height", type=int, default=18)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--no-sprites", action="store_true", help="Skip sprite generation")
    parser.add_argument("--output", "-o", default=None)
    args = parser.parse_args()

    print(f"[1/3] Generating tilemap from: {args.description}")
    tilemap = generate_tilemap(args.description, args.width, args.height, args.seed)
    print(f"       Biome: {tilemap['biome']}, {len(tilemap['props'])} props, {len(tilemap['npcs'])} NPCs")

    # Save tilemap JSON where the RPG can load it
    map_name = tilemap['biome'] + '_' + str(abs(hash(args.description)) % 10000)
    map_path = OUTPUT_DIR / "maps" / f"{map_name}.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(map_path, 'w') as f:
        json.dump(tilemap, f, indent=2)
    print(f"       Saved: {map_path}")

    # Check what sprites are needed
    print(f"\n[2/3] Checking sprite assets...")
    needed = get_needed_sprites(tilemap)
    if needed:
        print(f"       {len(needed)} sprites needed:")
        for s in needed:
            print(f"         - {s['name']} ({s['category']})")
        if not args.no_sprites:
            # Import and run sprite pipeline
            try:
                from sprite_pipeline import run_pipeline
                for job in needed:
                    run_pipeline(
                        prompt=job['prompt'],
                        category=job['category'],
                        name=job['name'],
                        variations=job['variations'],
                        target_size=tuple(job['target_size']),
                        n_colors=job['colors'],
                    )
            except ImportError:
                print("       [!] sprite_pipeline not available, skipping generation")
                print("       Run: python sprite_pipeline.py batch <sprites.json>")
        else:
            print("       Skipping sprite generation (--no-sprites)")
    else:
        print("       All sprites already exist!")

    print(f"\n[3/3] Level ready!")
    print(f"       Map: {map_path}")
    print(f"       Load in RPG: import map JSON and pass to RPGRenderer")
    print(f"\n  To play: npm run dev → open /rpg.html")


if __name__ == "__main__":
    main()
