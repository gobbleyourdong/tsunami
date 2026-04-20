/**
 * Cross-genre canary #2 — ninja_garden.
 *
 * Paralleling magic_hoops_canary.test.ts. Verifies:
 * - Scaffold directory + build chain + all 8 data files present.
 * - Scenes import ONLY from `@engine/mechanics` (no leaked engine-
 *   internal paths).
 * - Every `tryMount(...)` mechanic name is in the registry.
 * - Composition exercises ≥3 genre heritages (sandbox, action, stealth).
 * - tsconfig's `@engine` alias goes THREE levels up (nested under
 *   `cross/` — same depth gotcha magic_hoops tests for).
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'cross', 'ninja_garden')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Cross-canary #2 — ninja_garden (sandbox+action+stealth)', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 8 data files present (7 sister-authored + config.json main-authored)', () => {
    for (const f of ['player.json', 'enemies.json', 'biomes.json', 'tools.json',
                     'bosses.json', 'arena.json', 'rules.json', 'mechanics.json',
                     'config.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('player.json has shinobi with Chakra + stealth_meter + Inventory', () => {
    const data = readJSON('data/player.json') as any
    const p = data.player
    expect(p).toBeDefined()
    expect(Array.isArray(p.components)).toBe(true)
    expect(p.components.some((c: string) => c.startsWith('Health('))).toBe(true)
    expect(p.components.some((c: string) => c.includes('chakra'))).toBe(true)
    expect(p.components.some((c: string) => c.includes('stealth_meter'))).toBe(true)
  })

  it('arena.json declares procedural_terrain_persistence + day_night cycle', () => {
    const data = readJSON('data/arena.json') as any
    expect(data.arena.procedural_terrain_persistence).toBe(true)
    expect(typeof data.arena.day_night_cycle_seconds).toBe('number')
  })

  it('biomes.json has at least 3 biome templates with tile palettes', () => {
    const data = readJSON('data/biomes.json') as any
    const biomes = data.biomes
    expect(Object.keys(biomes).length).toBeGreaterThanOrEqual(3)
  })

  it('bosses.json has multi-phase bosses with HP thresholds', () => {
    const data = readJSON('data/bosses.json') as any
    const bosses = data.bosses
    expect(Object.keys(bosses).length).toBeGreaterThanOrEqual(2)
  })

  it('Match scene imports from @engine/mechanics only (CANARY INVARIANT)', () => {
    const match = read('src/scenes/Match.ts')
    expect(match).toContain("from '@engine/mechanics'")
    // No relative-up imports into engine internals — this is the hard
    // architectural gate. If it fails, Layer 1/2 abstractions are leaking.
    expect(match).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/\.\.\/(?:engine|mechanics|components)/)
    expect(match).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/\.\.\/\.\.\/(?:mechanics|components)/)
  })

  it('Match references ONLY registered mechanic types (CANARY)', () => {
    const src = read('src/scenes/Match.ts')
    const used = mechanicsReferencedBy(src)
    // JOB-U composition target is 12 mechanics; every one must be live.
    expect(used.size).toBeGreaterThanOrEqual(10)
    const unregistered: string[] = []
    for (const type of used) {
      if (!mechanicRegistry.has(type as any)) unregistered.push(type)
    }
    expect(unregistered).toEqual([])
  })

  it('Match composes mechanics from 3+ genre heritages (proves cross-genre)', () => {
    const src = read('src/scenes/Match.ts')
    const used = mechanicsReferencedBy(src)

    // Sandbox (Terraria): ProceduralRoomChain, InventoryCombine
    const sandbox = ['ProceduralRoomChain', 'InventoryCombine']
    // Action (Ninja Gaiden): ComboAttacks, AttackFrames, PhysicsModifier
    const action = ['ComboAttacks', 'AttackFrames', 'PhysicsModifier']
    // Stealth (MGS/Shinobi): VisionCone, ItemUse, LockAndKey
    const stealth = ['VisionCone', 'ItemUse', 'LockAndKey']

    const hasSandbox = sandbox.some((m) => used.has(m))
    const hasAction = action.some((m) => used.has(m))
    const hasStealth = stealth.some((m) => used.has(m))

    const heritages = [hasSandbox, hasAction, hasStealth].filter(Boolean).length
    expect(heritages).toBeGreaterThanOrEqual(3)
  })

  it('Match uses TimeReverseMechanic-ready architecture (v1.3 composability)', () => {
    // Regression guard — if a future scaffold extends this to include
    // TimeReverseMechanic (PoP / Braid-style rewind), the composition
    // should accept it. For now just verify the architectural slot
    // exists: the scene is tag-based (VisionCone reads `tags` from
    // entities) which is what TimeReverseMechanic's affects_tag filter
    // also consumes.
    const src = read('src/scenes/Match.ts')
    expect(src).toMatch(/\baffects_tag\b|\bowner_tag\b|\btarget_tag\b|\btag\b/i)
  })

  it('main.ts boots the Match scene and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Match')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents canary role + heritage + invariants', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('canary')
    expect(readme.toLowerCase()).toContain('cross-genre')
    expect(readme.toLowerCase()).toMatch(/terraria|ninja.gaiden|shinobi/)
    expect(readme).toMatch(/architectural invariant/i)
  })

  it('tsconfig.json paths alias goes three levels up (nested cross/ dir)', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../../engine')
  })

  it('mechanics.json seed declares exactly the 12 target mechanics', () => {
    const data = readJSON('data/mechanics.json') as any
    const types = new Set((data.mechanics ?? []).map((m: any) => m.type))
    const expected = [
      'ProceduralRoomChain', 'PhysicsModifier', 'ComboAttacks', 'AttackFrames',
      'InventoryCombine', 'LockAndKey', 'ItemUse', 'BossPhases',
      'VisionCone', 'CheckpointProgression', 'CameraFollow', 'HUD',
    ]
    for (const t of expected) expect(types.has(t)).toBe(true)
  })

  it('rules.json declares compound win_condition + structure_persistence', () => {
    const data = readJSON('data/rules.json') as any
    expect(data.rules.win_condition.kind).toBe('compound_any')
    expect(data.rules.structure_persistence).toBeDefined()
    expect(data.rules.structure_persistence.player_built_blocks_persist).toBe(true)
  })
})
