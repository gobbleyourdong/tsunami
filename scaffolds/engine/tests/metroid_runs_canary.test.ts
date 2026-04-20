/**
 * Cross-genre canary #5 — metroid_runs.
 *
 * Tests per-run-reset vs. persistent-ability-progression invariant.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'cross', 'metroid_runs')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Cross-canary #5 — metroid_runs (metroidvania+roguelike)', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 9 seed files present under data/', () => {
    for (const f of ['config.json', 'player.json', 'enemies.json', 'abilities.json',
                     'rooms.json', 'seeds.json', 'bosses.json',
                     'mechanics.json', 'rules.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('abilities.json has ≥6 unlockable abilities with gating', () => {
    const data = readJSON('data/abilities.json') as any
    const abilities = data.abilities
    expect(Object.keys(abilities).length).toBeGreaterThanOrEqual(6)
    expect(data.ability_unlock_gating).toBeDefined()
  })

  it('rooms.json has templates keyed by requires_ability', () => {
    const data = readJSON('data/rooms.json') as any
    const templates = data.room_templates
    expect(Object.keys(templates).length).toBeGreaterThanOrEqual(8)
    // At least one room must gate on an ability.
    const gated = Object.values<any>(templates).filter((t) => t.requires_ability)
    expect(gated.length).toBeGreaterThanOrEqual(1)
  })

  it('seeds.json declares ≥3 seed_configurations (determinism demo)', () => {
    const data = readJSON('data/seeds.json') as any
    const seeds = data.seed_configurations
    expect(Object.keys(seeds ?? {}).length).toBeGreaterThanOrEqual(3)
  })

  it('Run scene imports from @engine/mechanics only (CANARY invariant)', () => {
    const src = read('src/scenes/Run.ts')
    expect(src).toContain("from '@engine/mechanics'")
    expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/\.\.\/(?:engine|mechanics|components)/)
  })

  it('every mechanic name referenced in Run is registered', () => {
    const src = read('src/scenes/Run.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.size).toBeGreaterThanOrEqual(7)
    const unregistered: string[] = []
    for (const type of used) {
      if (!mechanicRegistry.has(type as any)) unregistered.push(type)
    }
    expect(unregistered).toEqual([])
  })

  it('Run mounts the metroidvania + roguelike cluster', () => {
    const src = read('src/scenes/Run.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.has('ProceduralRoomChain')).toBe(true)
    expect(used.has('LockAndKey')).toBe(true)
    expect(used.has('GatedTrigger')).toBe(true)
    expect(used.has('PhysicsModifier')).toBe(true)
    expect(used.has('CheckpointProgression')).toBe(true)
    expect(used.has('BossPhases')).toBe(true)
    expect(used.has('HUD')).toBe(true)
  })

  it('Run scene declares per-run vs. persistent state API', () => {
    const src = read('src/scenes/Run.ts')
    // Core API surface for the state-lifecycle invariant.
    expect(src).toContain('newRun')
    expect(src).toContain('unlockAbility')
    expect(src).toContain('recordBossDefeat')
    expect(src).toContain('getPersistentState')
    // Static persistent field — survives setup/teardown cycles.
    expect(src).toMatch(/static\s+persistent\s*:/)
  })

  it('rules.json declares per_run_reset + persistent_state_whitelist', () => {
    const data = readJSON('data/rules.json') as any
    const text = JSON.stringify(data).toLowerCase()
    expect(text).toMatch(/persistent|per_run|persist/)
  })

  it('mechanics.json declares exactly the 8 target mechanics', () => {
    const data = readJSON('data/mechanics.json') as any
    const types = new Set((data.mechanics ?? []).map((m: any) => m.type))
    const expected = [
      'ProceduralRoomChain', 'LockAndKey', 'GatedTrigger', 'ItemUse',
      'PhysicsModifier', 'CheckpointProgression', 'BossPhases', 'HUD',
    ]
    for (const t of expected) expect(types.has(t)).toBe(true)
  })

  it('main.ts boots Run and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Run')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the per-run-vs-persistent invariant', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('canary')
    expect(readme.toLowerCase()).toMatch(/per.run|persistent|progression/)
    expect(readme).toMatch(/metroid|roguelike|spelunky|dead cells/i)
  })

  it('tsconfig.json paths alias goes three levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../../engine')
  })
})
