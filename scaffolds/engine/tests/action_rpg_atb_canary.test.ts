/**
 * Cross-genre canary #4 — action_rpg_atb.
 *
 * First canary with TWO scenes (Field + Battle). Tests scene-boundary
 * state persistence invariant that magic_hoops / ninja_garden /
 * rhythm_fighter don't cover.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'cross', 'action_rpg_atb')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Cross-canary #4 — action_rpg_atb (action_adventure + jrpg)', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 9 seed files present under data/', () => {
    for (const f of ['config.json', 'player.json', 'party.json', 'rooms.json',
                     'enemies.json', 'battles.json', 'equipment.json',
                     'mechanics.json', 'rules.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('TWO scenes exist (Field + Battle) — first multi-scene canary', () => {
    expect(existsSync(join(SCAFFOLD, 'src', 'scenes', 'Field.ts'))).toBe(true)
    expect(existsSync(join(SCAFFOLD, 'src', 'scenes', 'Battle.ts'))).toBe(true)
  })

  it('both scenes import from @engine/mechanics only (CANARY invariant)', () => {
    for (const scene of ['Field', 'Battle']) {
      const src = read(`src/scenes/${scene}.ts`)
      expect(src).toContain("from '@engine/mechanics'")
      expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/\.\.\/(?:engine|mechanics|components)/)
    }
  })

  it('every mechanic name referenced across scenes is registered', () => {
    const all = new Set<string>()
    for (const scene of ['Field', 'Battle']) {
      const src = read(`src/scenes/${scene}.ts`)
      for (const m of mechanicsReferencedBy(src)) all.add(m)
    }
    expect(all.size).toBeGreaterThanOrEqual(8)
    const unregistered: string[] = []
    for (const type of all) {
      if (!mechanicRegistry.has(type as any)) unregistered.push(type)
    }
    expect(unregistered).toEqual([])
  })

  it('Field scene mounts the action-adventure heritage cluster', () => {
    const src = read('src/scenes/Field.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.has('RoomGraph')).toBe(true)
    expect(used.has('LockAndKey')).toBe(true)
    expect(used.has('ItemUse')).toBe(true)
    expect(used.has('CameraFollow')).toBe(true)
    expect(used.has('PartyComposition')).toBe(true)
    expect(used.has('HUD')).toBe(true)
  })

  it('Battle scene mounts the JRPG heritage cluster', () => {
    const src = read('src/scenes/Battle.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.has('ATBCombat')).toBe(true)
    expect(used.has('PartyComposition')).toBe(true)
    expect(used.has('EquipmentLoadout')).toBe(true)
    expect(used.has('BossPhases')).toBe(true)
  })

  it('PartyComposition mounted in BOTH scenes (scene-boundary invariant)', () => {
    const fieldSrc = read('src/scenes/Field.ts')
    const battleSrc = read('src/scenes/Battle.ts')
    expect(mechanicsReferencedBy(fieldSrc).has('PartyComposition')).toBe(true)
    expect(mechanicsReferencedBy(battleSrc).has('PartyComposition')).toBe(true)
  })

  it('handoff API exists (Field.handoffToBattle / Battle.snapshotForField)', () => {
    const fieldSrc = read('src/scenes/Field.ts')
    const battleSrc = read('src/scenes/Battle.ts')
    expect(fieldSrc).toContain('handoffToBattle')
    expect(battleSrc).toContain('snapshotForField')
  })

  it('main.ts boots Field (not Battle) and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Field')
    expect(main).toContain('Battle')
    expect(main).toContain('@engine/mechanics')
    // Default active scene should be 'field' — entering via Battle
    // would skip the scene-transition handoff.
    expect(main).toMatch(/let\s+active\s*:\s*SceneKey\s*=\s*['"]field['"]/)
  })

  it('rules.json declares scene-transition rules', () => {
    const data = readJSON('data/rules.json') as any
    const text = JSON.stringify(data).toLowerCase()
    expect(text).toMatch(/transition|enemy_contact|battle|field/)
  })

  it('mechanics.json seed declares exactly the 9 target mechanics', () => {
    const data = readJSON('data/mechanics.json') as any
    const types = new Set((data.mechanics ?? []).map((m: any) => m.type))
    const expected = [
      'RoomGraph', 'LockAndKey', 'ItemUse', 'CameraFollow',
      'ATBCombat', 'PartyComposition', 'EquipmentLoadout',
      'BossPhases', 'HUD',
    ]
    for (const t of expected) expect(types.has(t)).toBe(true)
  })

  it('README documents scene-boundary state persistence invariant', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('canary')
    expect(readme.toLowerCase()).toMatch(/scene.boundary|persistence/)
    expect(readme).toMatch(/zelda.*ff|final fantasy|atb/i)
  })

  it('tsconfig.json paths alias goes three levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../../engine')
  })
})
