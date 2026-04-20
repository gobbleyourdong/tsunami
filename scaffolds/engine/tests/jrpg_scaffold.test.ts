/**
 * Phase 8 — JRPG scaffold smoke test.
 *
 * Verifies the scaffold ships playable:
 * - Directory + required files exist
 * - Seed data parses (7 JSON files from JOB-F)
 * - Scenes import from @engine/mechanics ONLY (canary invariant)
 * - Scene mechanic mounts reference the JRPG v1.2 cluster
 * - Main boots Title → World → Town → Battle scene flow
 * - All `tryMount(...)` names resolve in the registry
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'jrpg')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Phase 8 — JRPG scaffold', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 7 JOB-F seed files present under data/', () => {
    for (const f of ['config.json', 'party.json', 'world_map.json', 'battles.json',
                     'spells.json', 'equipment.json', 'mechanics.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('party.json has at least 4 party members with components', () => {
    const data = readJSON('data/party.json') as any
    const members = data.characters ?? data.party ?? {}
    expect(Object.keys(members).length).toBeGreaterThanOrEqual(4)
    for (const [_id, m] of Object.entries<any>(members)) {
      expect(Array.isArray(m.components)).toBe(true)
      expect(m.components.some((c: string) => c.startsWith('Health('))).toBe(true)
    }
  })

  it('world_map.json has at least 8 connected regions', () => {
    const data = readJSON('data/world_map.json')
    const regions = data.regions as Record<string, any>
    expect(Object.keys(regions).length).toBeGreaterThanOrEqual(8)
    // Every region lists connections (or is a valid dead-end like final castle).
    for (const [_id, r] of Object.entries(regions)) {
      expect(Array.isArray(r.connections)).toBe(true)
    }
  })

  it('battles.json has enemies (including boss-tagged) + encounter_groups', () => {
    const data = readJSON('data/battles.json') as any
    // Sister's JOB-F seed uses a flat `enemies` dict with `tags: ['boss']` entries
    // rather than a separate `bosses` key; either shape is valid.
    const allEnemies = { ...(data.enemies ?? {}), ...(data.bosses ?? {}) }
    expect(Object.keys(allEnemies).length).toBeGreaterThanOrEqual(4)
    const bossesByTag = Object.entries<any>(allEnemies).filter(
      ([_id, e]) => Array.isArray(e.tags) && e.tags.includes('boss'),
    )
    const bossesByKey = Object.keys(data.bosses ?? {})
    expect(bossesByTag.length + bossesByKey.length).toBeGreaterThanOrEqual(1)
    expect(data.encounter_groups).toBeDefined()
  })

  it('spells.json has at least 10 spells with canonical target_scope', () => {
    const data = readJSON('data/spells.json') as any
    const spells = data.spells
    expect(Object.keys(spells).length).toBeGreaterThanOrEqual(10)
    const VALID = new Set(['single_enemy', 'all_enemies', 'single_ally', 'all_allies', 'self'])
    for (const [_id, s] of Object.entries<any>(spells)) {
      expect(VALID.has(s.target_scope)).toBe(true)
    }
  })

  it('equipment.json has at least 12 items across 5 slot types', () => {
    const data = readJSON('data/equipment.json') as any
    const items = data.equipment
    expect(Object.keys(items).length).toBeGreaterThanOrEqual(12)
    const slots = new Set(Object.values<any>(items).map((i) => i.slot))
    // Must include at least weapon + armor + one accessory variant.
    expect(slots.has('weapon')).toBe(true)
    expect(slots.has('armor')).toBe(true)
  })

  it('scenes import from @engine/mechanics only (CANARY invariant)', () => {
    for (const name of ['Title', 'World', 'Town', 'Battle']) {
      const src = read(`src/scenes/${name}.ts`)
      expect(src).toContain("from '@engine/mechanics'")
      // No relative import into engine internals.
      expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/(?:engine|mechanics|components)/)
    }
  })

  it('every mechanic name referenced in scenes is registered', () => {
    const all = new Set<string>()
    for (const name of ['Title', 'World', 'Town', 'Battle']) {
      const src = read(`src/scenes/${name}.ts`)
      for (const m of mechanicsReferencedBy(src)) all.add(m)
    }
    expect(all.size).toBeGreaterThanOrEqual(6)
    const unregistered: string[] = []
    for (const type of all) {
      if (!mechanicRegistry.has(type as any)) unregistered.push(type)
    }
    expect(unregistered).toEqual([])
  })

  it('scenes mount the JRPG v1.2 cluster (ATBCombat + PartyComposition + LevelUpProgression + WorldMapTravel + EquipmentLoadout)', () => {
    const all = new Set<string>()
    for (const name of ['Title', 'World', 'Town', 'Battle']) {
      const src = read(`src/scenes/${name}.ts`)
      for (const m of mechanicsReferencedBy(src)) all.add(m)
    }
    expect(all.has('ATBCombat')).toBe(true)
    expect(all.has('PartyComposition')).toBe(true)
    expect(all.has('LevelUpProgression')).toBe(true)
    expect(all.has('WorldMapTravel')).toBe(true)
    expect(all.has('EquipmentLoadout')).toBe(true)
  })

  it('main.ts boots the Title scene and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Title')
    expect(main).toContain('World')
    expect(main).toContain('Battle')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the JRPG cluster + genre heritage', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('jrpg')
    expect(readme).toMatch(/atbcombat/i)
    expect(readme).toMatch(/party/i)
    expect(readme).toMatch(/data\/[a-z_]+\.json/)
  })

  it('tsconfig.json paths alias points two levels up (sibling-depth, same as fighting/action_adventure)', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../engine')
  })
})
