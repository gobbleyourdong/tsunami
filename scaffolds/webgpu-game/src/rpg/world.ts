/**
 * RPG World — tile-based map with layers, props, NPCs, and collision.
 * Top-down 2.5D: tiles on ground, sprites for characters/objects.
 */

export type TileType = 'grass' | 'darkgrass' | 'flowers' | 'path' | 'stone' | 'water' | 'sand' | 'lava' | 'wood'

export interface PropDef {
  type: string      // sprite name (prop_tree, prop_rock, prop_house, prop_well)
  x: number         // tile X
  y: number         // tile Y
  solid: boolean    // blocks movement?
  interact?: string // interaction type (talk, open, examine)
}

export interface NPCDef {
  id: string
  name: string
  sprite: string    // sprite name
  x: number
  y: number
  dialog?: string[] // dialog lines
  patrol?: [number, number][]  // patrol waypoints (tile coords)
  hostile?: boolean
}

export interface WorldMap {
  name: string
  width: number     // tiles
  height: number    // tiles
  tileSize: number  // pixels per tile
  layers: {
    ground: TileType[][]    // base terrain
    overlay?: TileType[][]  // paths, decorations on top of ground
  }
  props: PropDef[]
  npcs: NPCDef[]
  playerStart: [number, number]
  exits: { x: number; y: number; target: string; spawnX: number; spawnY: number }[]
}

/** Check if a tile is walkable. */
export function isWalkable(tile: TileType): boolean {
  return tile !== 'water' && tile !== 'lava'
}

/** Check if a position is blocked by props. */
export function isBlockedByProp(map: WorldMap, tileX: number, tileY: number): boolean {
  return map.props.some(p => p.solid && Math.floor(p.x) === tileX && Math.floor(p.y) === tileY)
}

/** Check if a tile position is valid for movement. */
export function canMoveTo(map: WorldMap, tileX: number, tileY: number): boolean {
  if (tileX < 0 || tileY < 0 || tileX >= map.width || tileY >= map.height) return false
  const tile = map.layers.ground[tileY]?.[tileX]
  if (!tile || !isWalkable(tile)) return false
  if (isBlockedByProp(map, tileX, tileY)) return false
  return true
}

// ── Map Definitions ──────────────────────────────────────────────

export function createVillageMap(): WorldMap {
  const W = 24, H = 18
  const ground: TileType[][] = []

  // Fill with grass
  for (let y = 0; y < H; y++) {
    ground[y] = []
    for (let x = 0; x < W; x++) {
      ground[y][x] = 'grass'
    }
  }

  // Forest border (dark grass)
  for (let x = 0; x < W; x++) {
    ground[0][x] = 'darkgrass'
    ground[1][x] = 'darkgrass'
    ground[H-1][x] = 'darkgrass'
    ground[H-2][x] = 'darkgrass'
  }
  for (let y = 0; y < H; y++) {
    ground[y][0] = 'darkgrass'
    ground[y][1] = 'darkgrass'
    ground[y][W-1] = 'darkgrass'
    ground[y][W-2] = 'darkgrass'
  }

  // Central path (horizontal)
  for (let x = 3; x < W - 3; x++) {
    ground[8][x] = 'path'
    ground[9][x] = 'path'
  }
  // Vertical path to houses
  for (let y = 4; y < 13; y++) {
    ground[y][11] = 'path'
    ground[y][12] = 'path'
  }

  // Flower patches
  ground[5][6] = 'flowers'; ground[5][7] = 'flowers'; ground[6][6] = 'flowers'
  ground[12][16] = 'flowers'; ground[12][17] = 'flowers'; ground[13][17] = 'flowers'

  // Pond
  ground[13][5] = 'water'; ground[13][6] = 'water'
  ground[14][5] = 'water'; ground[14][6] = 'water'; ground[14][7] = 'water'

  return {
    name: 'Oakvale Village',
    width: W,
    height: H,
    tileSize: 32,
    layers: { ground },
    props: [
      // Houses
      { type: 'prop_house', x: 7, y: 4, solid: true },
      { type: 'prop_house', x: 15, y: 4, solid: true },
      { type: 'prop_house', x: 7, y: 12, solid: true },

      // Well in town center
      { type: 'prop_well', x: 11, y: 6, solid: true, interact: 'examine' },

      // Trees (forest border)
      { type: 'prop_tree', x: 2, y: 2, solid: true },
      { type: 'prop_tree', x: 4, y: 1, solid: true },
      { type: 'prop_tree', x: 6, y: 2, solid: true },
      { type: 'prop_tree', x: 18, y: 2, solid: true },
      { type: 'prop_tree', x: 20, y: 1, solid: true },
      { type: 'prop_tree', x: 21, y: 3, solid: true },
      { type: 'prop_tree', x: 3, y: 14, solid: true },
      { type: 'prop_tree', x: 2, y: 16, solid: true },
      { type: 'prop_tree', x: 19, y: 15, solid: true },
      { type: 'prop_tree', x: 21, y: 14, solid: true },

      // Rocks
      { type: 'prop_rock', x: 17, y: 10, solid: true },
      { type: 'prop_rock', x: 9, y: 14, solid: false },
    ],
    npcs: [
      {
        id: 'elder',
        name: 'Elder Aldric',
        sprite: 'npc_elder',
        x: 12, y: 7,
        dialog: [
          'Welcome, brave adventurer.',
          'Our village has been plagued by monsters from the dark forest.',
          'Will you help us? Seek the wolves to the north.',
        ],
      },
      {
        id: 'merchant',
        name: 'Merchant Greta',
        sprite: 'npc_merchant',
        x: 16, y: 8,
        dialog: [
          'Fine wares for sale! Well... I would have wares if the roads were safe.',
          'Bring me 3 wolf pelts and I\'ll craft you a shield!',
        ],
      },
      {
        id: 'guard',
        name: 'Guard Tomas',
        sprite: 'npc_guard',
        x: 8, y: 9,
        dialog: [
          'Halt! Oh, it\'s you. The elder was looking for you.',
          'Be careful near the forest edge. Wolves have been spotted.',
        ],
        patrol: [[8, 9], [14, 9], [14, 9], [8, 9]],
      },
    ],
    playerStart: [12, 10],
    exits: [
      { x: 12, y: 0, target: 'forest', spawnX: 12, spawnY: 16 },
    ],
  }
}

export function createForestMap(): WorldMap {
  const W = 24, H = 18
  const ground: TileType[][] = []

  for (let y = 0; y < H; y++) {
    ground[y] = []
    for (let x = 0; x < W; x++) {
      ground[y][x] = 'darkgrass'
    }
  }

  // Clearing in center
  for (let y = 6; y < 14; y++) {
    for (let x = 6; x < 18; x++) {
      ground[y][x] = 'grass'
    }
  }

  // Path from south entrance
  for (let y = 14; y < H; y++) {
    ground[y][11] = 'path'
    ground[y][12] = 'path'
  }

  return {
    name: 'Dark Forest',
    width: W,
    height: H,
    tileSize: 32,
    layers: { ground },
    props: [
      // Dense tree border
      ...Array.from({ length: 20 }, (_, i) => ({
        type: 'prop_tree' as string,
        x: 2 + (i % 5) * 4 + Math.random() * 2,
        y: 1 + Math.floor(i / 5) * 4 + Math.random() * 2,
        solid: true,
      })).filter(t => t.x < 5 || t.x > 18 || t.y < 5 || t.y > 14),  // not in clearing
      { type: 'prop_rock', x: 8, y: 8, solid: true },
      { type: 'prop_rock', x: 14, y: 11, solid: false },
    ],
    npcs: [
      // Wolves in the clearing
      { id: 'wolf1', name: 'Wolf', sprite: 'rpg_wolf', x: 9, y: 8, hostile: true, dialog: [] },
      { id: 'wolf2', name: 'Wolf', sprite: 'rpg_wolf', x: 13, y: 9, hostile: true, dialog: [] },
      { id: 'wolf3', name: 'Wolf', sprite: 'rpg_wolf', x: 11, y: 11, hostile: true, dialog: [] },
    ],
    playerStart: [12, 16],
    exits: [
      { x: 12, y: 17, target: 'village', spawnX: 12, spawnY: 1 },
    ],
  }
}
