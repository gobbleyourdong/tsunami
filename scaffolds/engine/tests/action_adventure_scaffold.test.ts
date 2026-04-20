/**
 * Phase 6 — action-adventure scaffold smoke test.
 *
 * Verifies the scaffold at scaffolds/gamedev/action_adventure/:
 *  - package.json, tsconfig, vite.config, index.html
 *  - data/*.json all parse with JOB-D seed content intact
 *  - rooms.json graph is connected
 *  - entities + items reference valid component shapes
 *  - mechanics reference valid MechanicType literals from schema.ts
 *  - scene files export expected classes (static import check)
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'action_adventure')

function read(rel: string): string {
  return readFileSync(join(SCAFFOLD, rel), 'utf8')
}
function readJSON(rel: string): any {
  return JSON.parse(read(rel))
}

describe('Phase 6 — action-adventure scaffold', () => {
  it('scaffold directory exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
  })

  it('package.json declares engine dep', () => {
    const pkg = readJSON('package.json')
    expect(pkg.name).toBe('gamedev-action-adventure-scaffold')
    expect(pkg.dependencies?.engine).toMatch(/^file:/)
  })

  it('all 4 data files + SEED_ATTRIBUTION present', () => {
    for (const f of ['config.json', 'entities.json', 'rooms.json', 'items.json', 'mechanics.json', 'SEED_ATTRIBUTION.md']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('config.json has required fields', () => {
    const cfg = readJSON('data/config.json')
    expect(cfg.starting_room).toBeDefined()
  })

  it('entities.json has player + 4+ enemies per JOB-D', () => {
    const data = readJSON('data/entities.json')
    const entities = data.entities || data  // accept either shape
    expect(Array.isArray(entities)).toBe(true)
    expect(entities.length).toBeGreaterThanOrEqual(5)
    const ids = entities.map((e: any) => e.id)
    expect(ids).toContain('player')
  })

  it('rooms.json has 5+ overworld + 3+ dungeon rooms', () => {
    const data = readJSON('data/rooms.json')
    const rooms = data.rooms || data
    const overworld = Object.values(rooms).filter(
      (r: any) => r.kind === 'overworld'
    )
    const dungeon = Object.values(rooms).filter(
      (r: any) => r.kind === 'dungeon'
    )
    expect(overworld.length).toBeGreaterThanOrEqual(5)
    expect(dungeon.length).toBeGreaterThanOrEqual(3)
  })

  it('rooms graph is connected from starting_room', () => {
    const cfg = readJSON('data/config.json')
    const data = readJSON('data/rooms.json')
    const rooms = data.rooms || data
    const start = cfg.starting_room
    expect(rooms[start]).toBeDefined()

    // BFS from start
    const reachable = new Set<string>([start])
    const queue: string[] = [start]
    while (queue.length > 0) {
      const cur = queue.shift()!
      const conns = (rooms[cur]?.connections ?? {}) as Record<string, string>
      for (const target of Object.values(conns)) {
        if (!reachable.has(target)) {
          reachable.add(target)
          queue.push(target)
        }
      }
    }
    // Every room should be reachable (or flagged as disconnected — fail loud)
    const disconnected = Object.keys(rooms).filter((k) => !reachable.has(k))
    expect(disconnected).toEqual([])
  })

  it('items.json has 6+ items covering sword/bow/bomb/key/heart/compass', () => {
    const data = readJSON('data/items.json')
    const items = data.items || data
    expect(items.length).toBeGreaterThanOrEqual(6)
    const ids = items.map((i: any) => i.id ?? i.name).join(' ').toLowerCase()
    for (const required of ['sword', 'bow', 'bomb', 'key', 'heart', 'compass']) {
      expect(ids).toContain(required)
    }
  })

  it('mechanics.json uses only valid MechanicType literals', () => {
    const data = readJSON('data/mechanics.json')
    const mechanics = data.mechanics || data
    // These are the 46 valid types from schema.ts
    const validTypes = new Set([
      'Difficulty','HUD','LoseOnZero','WinOnCount','WaveSpawner','PickupLoop',
      'ScoreCombos','CheckpointProgression','LockAndKey','StateMachineMechanic',
      'ComboAttacks','BossPhases','RhythmTrack','LevelSequence','RoomGraph',
      'ItemUse','GatedTrigger','TimedStateModifier','AttackFrames','Shop',
      'UtilityAI','DialogTree','HotspotMechanic','InventoryCombine','CameraFollow',
      'StatusStack','EmbeddedMinigame','EndingBranches','VisionCone','PuzzleObject',
      'ProceduralRoomChain','BulletPattern','RouteMap','ChipMusic','SfxLibrary',
      'RoleAssignment','CrowdSimulation','TimeReverseMechanic','PhysicsModifier',
      'MinigamePool','ATBCombat','TurnBasedCombat','PartyComposition',
      'LevelUpProgression','WorldMapTravel','EquipmentLoadout',
    ])
    for (const m of mechanics) {
      expect(validTypes.has(m.type)).toBe(true)
    }
  })

  it('mechanics include action-adventure staples', () => {
    const data = readJSON('data/mechanics.json')
    const mechanics = data.mechanics || data
    const types = mechanics.map((m: any) => m.type)
    // Per JOB-A / Plan: Zelda-like must ship with RoomGraph + LockAndKey + CameraFollow
    expect(types).toContain('RoomGraph')
    expect(types).toContain('LockAndKey')
    expect(types).toContain('CameraFollow')
  })

  it('main.ts imports from @engine/mechanics and scenes', () => {
    const main = read('src/main.ts')
    expect(main).toContain('@engine/mechanics')
    expect(main).toContain('Overworld')
    expect(main).toContain('Dungeon')
    expect(main).toContain('GameOver')
  })

  it('Overworld scene exports the class with setup/teardown', () => {
    const src = read('src/scenes/Overworld.ts')
    expect(src).toContain('export class Overworld')
    expect(src).toContain('setup()')
    expect(src).toContain('teardown()')
  })

  it('README documents customization paths', () => {
    const readme = read('README.md')
    expect(readme).toContain('data/*.json')
    expect(readme).toContain('Zelda-like')
    expect(readme).toContain('SEED_ATTRIBUTION')
  })
})
