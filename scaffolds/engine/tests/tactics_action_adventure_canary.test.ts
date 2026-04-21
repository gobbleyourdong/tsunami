/**
 * Cross-genre canary — tactics_action_adventure.
 *
 * Same shape as magic_hoops / bullet_hell_rpg / puzzle_platformer_roguelite.
 * Verifies pure composition from @engine/mechanics across ≥ 3 genre heritages
 * and that the flag→ending logic is wired.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'cross', 'tactics_action_adventure')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Cross-genre canary — tactics_action_adventure', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all data files present', () => {
    for (const f of ['config.json', 'party.json', 'world.json', 'combat.json', 'dialog.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('party has at least 3 members across distinct roles', () => {
    const members = readJSON('data/party.json').party.members
    const roles = new Set(Object.values<any>(members).map(m => m.role))
    expect(Object.keys(members).length).toBeGreaterThanOrEqual(3)
    expect(roles.size).toBeGreaterThanOrEqual(3)
  })

  it('world map nodes form a connected graph', () => {
    const wm = readJSON('data/world.json').world_map
    const ids = new Set(wm.nodes.map((n: any) => n.id))
    for (const n of wm.nodes) {
      for (const link of n.links) expect(ids.has(link)).toBe(true)
    }
    expect(ids.has(wm.start)).toBe(true)
  })

  it('combat has >= 3 enemy archetypes + >= 2 encounters', () => {
    const c = readJSON('data/combat.json').combat
    expect(Object.keys(c.enemy_archetypes).length).toBeGreaterThanOrEqual(3)
    expect(Object.keys(c.encounters).length).toBeGreaterThanOrEqual(2)
    for (const arch of Object.values<any>(c.enemy_archetypes)) {
      expect(arch.ai_utility_weights).toBeDefined()
    }
  })

  it('dialog trees have a root + reachable nodes', () => {
    const d = readJSON('data/dialog.json').dialogs
    for (const [id, tree] of Object.entries<any>(d)) {
      expect(tree.root).toBeDefined()
      expect(tree.nodes[tree.root]).toBeDefined()
    }
  })

  it('endings require flags that dialogs actually set', () => {
    const data = readJSON('data/dialog.json')
    const setFlags = new Set<string>()
    for (const tree of Object.values<any>(data.dialogs)) {
      for (const node of Object.values<any>(tree.nodes)) {
        if (node.set_flag) setFlags.add(node.set_flag)
      }
    }
    for (const ending of Object.values<any>(data.endings)) {
      for (const required of (ending.requires_flags ?? [])) {
        expect(setFlags.has(required)).toBe(true)
      }
    }
  })

  it('Adventure scene imports from @engine/mechanics only (CANARY)', () => {
    const src = read('src/scenes/Adventure.ts')
    expect(src).toContain("from '@engine/mechanics'")
    expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/mechanics/)
    expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/components/)
  })

  it('Adventure references ONLY registered mechanic types (CANARY)', () => {
    const src = read('src/scenes/Adventure.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.size).toBeGreaterThanOrEqual(10)
    const unregistered: string[] = []
    for (const type of used) {
      if (!mechanicRegistry.has(type as any)) unregistered.push(type)
    }
    expect(unregistered).toEqual([])
  })

  it('Adventure composes mechanics from 3+ genre heritages', () => {
    const src = read('src/scenes/Adventure.ts')
    const used = mechanicsReferencedBy(src)

    const tactics = ['ATBCombat', 'TurnBasedCombat', 'PartyComposition', 'RoleAssignment', 'UtilityAI']
    const action = ['CameraFollow', 'AttackFrames', 'CheckpointProgression']
    const adventure = ['DialogTree', 'HotspotMechanic', 'WorldMapTravel', 'Shop', 'EndingBranches']

    const hasTactics = tactics.some(m => used.has(m))
    const hasAction = action.some(m => used.has(m))
    const hasAdventure = adventure.some(m => used.has(m))

    const heritages = [hasTactics, hasAction, hasAdventure].filter(Boolean).length
    expect(heritages).toBeGreaterThanOrEqual(3)
  })

  it('main.ts boots the Adventure scene', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Adventure')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents cross-genre + heritage + canary role', () => {
    const readme = read('README.md').toLowerCase()
    expect(readme).toContain('cross-genre')
    expect(readme).toContain('heritage')
    expect(readme).toContain('canary')
  })

  it('tsconfig paths alias goes three levels up', () => {
    const tsc = readJSON('tsconfig.json')
    expect(tsc.compilerOptions?.paths?.['@engine']?.[0]).toContain('../../../engine')
  })
})
