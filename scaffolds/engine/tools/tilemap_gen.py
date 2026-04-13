#!/usr/bin/env python3
"""
Procedural tilemap generator — create RPG maps from text descriptions.

Usage:
  python tilemap_gen.py "medieval village with river, 3 houses, market square"
  python tilemap_gen.py "dark forest with clearing, cave entrance, wolves"
  python tilemap_gen.py "desert oasis with palm trees and ruins"
"""

import argparse
import json
import random
from pathlib import Path

# Tile types available in the engine
TILES = ['grass', 'darkgrass', 'flowers', 'path', 'stone', 'water', 'sand', 'lava', 'wood']

# Biome templates — base terrain distribution
BIOMES = {
    'village': {'base': 'grass', 'border': 'darkgrass', 'path': True, 'water_chance': 0.1},
    'forest': {'base': 'darkgrass', 'border': 'darkgrass', 'path': True, 'water_chance': 0.05},
    'desert': {'base': 'sand', 'border': 'sand', 'path': False, 'water_chance': 0.15},
    'dungeon': {'base': 'stone', 'border': 'stone', 'path': False, 'water_chance': 0.0},
    'cave': {'base': 'stone', 'border': 'stone', 'path': False, 'water_chance': 0.1},
    'lava': {'base': 'stone', 'border': 'stone', 'path': True, 'water_chance': 0.0},
    'swamp': {'base': 'darkgrass', 'border': 'darkgrass', 'path': True, 'water_chance': 0.3},
}

# Prop templates
PROP_SETS = {
    'village': ['prop_house', 'prop_well', 'prop_tree', 'prop_rock'],
    'forest': ['prop_tree', 'prop_rock'],
    'desert': ['prop_rock'],
    'dungeon': ['prop_rock'],
    'cave': ['prop_rock'],
}

# NPC templates
NPC_TEMPLATES = {
    'elder': {'sprite': 'npc_elder', 'name': 'Village Elder', 'hostile': False},
    'merchant': {'sprite': 'npc_merchant', 'name': 'Merchant', 'hostile': False},
    'guard': {'sprite': 'npc_guard', 'name': 'Guard', 'hostile': False},
    'wolf': {'sprite': 'rpg_wolf', 'name': 'Wolf', 'hostile': True},
    'spider': {'sprite': 'rpg_spider', 'name': 'Spider', 'hostile': True},
}


def detect_biome(description: str) -> str:
    desc = description.lower()
    if any(w in desc for w in ['village', 'town', 'settlement', 'hamlet']):
        return 'village'
    if any(w in desc for w in ['forest', 'woods', 'grove']):
        return 'forest'
    if any(w in desc for w in ['desert', 'sand', 'dunes', 'oasis']):
        return 'desert'
    if any(w in desc for w in ['dungeon', 'crypt', 'tomb']):
        return 'dungeon'
    if any(w in desc for w in ['cave', 'cavern', 'mine']):
        return 'cave'
    if any(w in desc for w in ['lava', 'volcano', 'fire']):
        return 'lava'
    if any(w in desc for w in ['swamp', 'marsh', 'bog']):
        return 'swamp'
    return 'village'


def detect_features(description: str) -> dict:
    """Parse description for features: houses, trees, enemies, water, etc."""
    desc = description.lower()
    features = {
        'houses': 0, 'trees': 0, 'rocks': 0, 'water': False,
        'npcs': [], 'enemies': [], 'path': False, 'clearing': False,
    }

    # Count explicit numbers
    import re
    for match in re.finditer(r'(\d+)\s+(house|building|cottage)', desc):
        features['houses'] = int(match.group(1))
    if features['houses'] == 0 and any(w in desc for w in ['house', 'building', 'cottage']):
        features['houses'] = 2

    for match in re.finditer(r'(\d+)\s+(tree|palm)', desc):
        features['trees'] = int(match.group(1))
    if features['trees'] == 0 and any(w in desc for w in ['tree', 'palm', 'forest']):
        features['trees'] = 8

    features['water'] = any(w in desc for w in ['river', 'lake', 'pond', 'oasis', 'water', 'stream'])
    features['path'] = any(w in desc for w in ['path', 'road', 'trail', 'street'])
    features['clearing'] = any(w in desc for w in ['clearing', 'open', 'square', 'plaza', 'market'])

    if any(w in desc for w in ['wolf', 'wolves']):
        features['enemies'].append(('wolf', 3))
    if any(w in desc for w in ['spider', 'spiders']):
        features['enemies'].append(('spider', 3))
    if any(w in desc for w in ['elder', 'sage', 'wizard']):
        features['npcs'].append('elder')
    if any(w in desc for w in ['merchant', 'shop', 'trader', 'market']):
        features['npcs'].append('merchant')
    if any(w in desc for w in ['guard', 'soldier', 'knight']):
        features['npcs'].append('guard')

    return features


def generate_tilemap(description: str, width: int = 24, height: int = 18, seed: int = -1) -> dict:
    """Generate a tilemap from a text description."""
    if seed >= 0:
        random.seed(seed)

    biome = detect_biome(description)
    features = detect_features(description)
    biome_cfg = BIOMES[biome]

    # Initialize ground
    ground = [[biome_cfg['base']] * width for _ in range(height)]

    # Border (2 tiles thick)
    for y in range(height):
        for x in range(width):
            if x < 2 or x >= width - 2 or y < 2 or y >= height - 2:
                ground[y][x] = biome_cfg['border']

    # Water feature
    if features['water'] or random.random() < biome_cfg['water_chance']:
        wx = random.randint(3, width - 6)
        wy = random.randint(height // 2, height - 5)
        for dy in range(2 + random.randint(0, 2)):
            for dx in range(2 + random.randint(0, 3)):
                if wy + dy < height - 2 and wx + dx < width - 2:
                    ground[wy + dy][wx + dx] = 'water'

    # Clearing
    if features['clearing']:
        cx, cy = width // 2, height // 2
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if 2 <= cy + dy < height - 2 and 2 <= cx + dx < width - 2:
                    ground[cy + dy][cx + dx] = 'grass' if biome != 'desert' else 'sand'

    # Path (horizontal through center)
    if features['path'] or biome_cfg['path']:
        py = height // 2
        for x in range(3, width - 3):
            ground[py][x] = 'path'
            ground[py + 1][x] = 'path'
        # Vertical path
        px = width // 2
        for y in range(4, height - 4):
            ground[y][px] = 'path'

    # Flower patches
    if biome in ['village', 'forest']:
        for _ in range(3):
            fx, fy = random.randint(3, width - 4), random.randint(3, height - 4)
            if ground[fy][fx] == 'grass':
                ground[fy][fx] = 'flowers'

    # Props
    props = []
    available_spots = [(x, y) for y in range(3, height - 3) for x in range(3, width - 3)
                       if ground[y][x] != 'water' and ground[y][x] != 'path']
    random.shuffle(available_spots)
    spot_idx = 0

    for _ in range(features['houses']):
        if spot_idx < len(available_spots):
            x, y = available_spots[spot_idx]; spot_idx += 1
            props.append({'type': 'prop_house', 'x': x, 'y': y, 'solid': True})

    for _ in range(features['trees']):
        if spot_idx < len(available_spots):
            x, y = available_spots[spot_idx]; spot_idx += 1
            props.append({'type': 'prop_tree', 'x': x, 'y': y, 'solid': True})

    # Random rocks
    for _ in range(random.randint(2, 5)):
        if spot_idx < len(available_spots):
            x, y = available_spots[spot_idx]; spot_idx += 1
            props.append({'type': 'prop_rock', 'x': x, 'y': y, 'solid': random.random() > 0.5})

    # NPCs
    npcs = []
    npc_id = 0
    path_spots = [(x, y) for y in range(3, height - 3) for x in range(3, width - 3)
                  if ground[y][x] == 'path' or ground[y][x] in ['grass', 'sand']]
    random.shuffle(path_spots)
    npc_spot_idx = 0

    for npc_type in features['npcs']:
        if npc_type in NPC_TEMPLATES and npc_spot_idx < len(path_spots):
            x, y = path_spots[npc_spot_idx]; npc_spot_idx += 1
            tmpl = NPC_TEMPLATES[npc_type]
            npcs.append({
                'id': f'{npc_type}_{npc_id}', 'name': tmpl['name'],
                'sprite': tmpl['sprite'], 'x': x, 'y': y,
                'hostile': tmpl['hostile'],
                'dialog': [f"Hello, traveler. I am the {tmpl['name']}."],
            })
            npc_id += 1

    for enemy_type, count in features['enemies']:
        if enemy_type in NPC_TEMPLATES:
            for i in range(count):
                if npc_spot_idx < len(path_spots):
                    x, y = path_spots[npc_spot_idx]; npc_spot_idx += 1
                    tmpl = NPC_TEMPLATES[enemy_type]
                    npcs.append({
                        'id': f'{enemy_type}_{npc_id}', 'name': tmpl['name'],
                        'sprite': tmpl['sprite'], 'x': x, 'y': y,
                        'hostile': True, 'dialog': [],
                    })
                    npc_id += 1

    # Player start (center of map, on walkable tile)
    player_start = [width // 2, height // 2 + 2]

    return {
        'name': description[:40],
        'width': width, 'height': height, 'tileSize': 32,
        'layers': {'ground': ground},
        'props': props,
        'npcs': npcs,
        'playerStart': player_start,
        'exits': [],
        'biome': biome,
        'description': description,
    }


def main():
    parser = argparse.ArgumentParser(description="Procedural tilemap generator")
    parser.add_argument("description", help="Text description of the map")
    parser.add_argument("--width", type=int, default=24)
    parser.add_argument("--height", type=int, default=18)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--output", "-o", default=None, help="Output JSON file")
    args = parser.parse_args()

    tilemap = generate_tilemap(args.description, args.width, args.height, args.seed)

    out_path = args.output or f"tilemap_{tilemap['biome']}.json"
    with open(out_path, 'w') as f:
        json.dump(tilemap, f, indent=2)

    print(f"Generated: {tilemap['name']}")
    print(f"  Biome: {tilemap['biome']}, Size: {args.width}x{args.height}")
    print(f"  Props: {len(tilemap['props'])}, NPCs: {len(tilemap['npcs'])}")
    print(f"  Saved: {out_path}")


if __name__ == "__main__":
    main()
