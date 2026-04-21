/**
 * Cross-genre canary — puzzle_platformer_roguelite.
 *
 * Same shape as magic_hoops / bullet_hell_rpg canaries. Verifies
 * pure composition from @engine/mechanics across ≥ 3 genre heritages.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'cross', 'puzzle_platformer_roguelite')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Cross-genre canary — puzzle_platformer_roguelite', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all data files present', () => {
    for (const f of ['config.json', 'player.json', 'rooms.json', 'relics.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('rooms.json has >= 5 blueprints across puzzle + platformer tags', () => {
    const data = readJSON('data/rooms.json')
    const pool = data.room_pool
    expect(Array.isArray(pool)).toBe(true)
    expect(pool.length).toBeGreaterThanOrEqual(5)
    const tagUnion = new Set<string>()
    for (const r of pool) for (const t of (r.tags ?? [])) tagUnion.add(t)
    expect(tagUnion.has('puzzle')).toBe(true)
    expect(tagUnion.has('platformer')).toBe(true)
  })

  it('at least one room has physics_mod and one has locks', () => {
    const pool = readJSON('data/rooms.json').room_pool
    expect(pool.some((r: any) => r.physics_mod)).toBe(true)
    expect(pool.some((r: any) => Array.isArray(r.locks) && r.locks.length > 0)).toBe(true)
  })

  it('relics.json has >= 4 relics across multiple tiers', () => {
    const relics = readJSON('data/relics.json').relics
    expect(Object.keys(relics).length).toBeGreaterThanOrEqual(4)
    const tiers = new Set(Object.values<any>(relics).map(r => r.tier))
    expect(tiers.size).toBeGreaterThanOrEqual(2)
  })

  it('chain declares length + rule', () => {
    const chain = readJSON('data/rooms.json').chain
    expect(typeof chain.length).toBe('number')
    expect(chain.length).toBeGreaterThan(0)
    expect(typeof chain.rule).toBe('string')
  })

  it('Run scene imports from @engine/mechanics only (CANARY)', () => {
    const src = read('src/scenes/Run.ts')
    expect(src).toContain("from '@engine/mechanics'")
    expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/mechanics/)
    expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/components/)
  })

  it('Run references ONLY registered mechanic types (CANARY)', () => {
    const src = read('src/scenes/Run.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.size).toBeGreaterThanOrEqual(8)
    const unregistered: string[] = []
    for (const type of used) {
      if (!mechanicRegistry.has(type as any)) unregistered.push(type)
    }
    expect(unregistered).toEqual([])
  })

  it('Run composes mechanics from 3+ genre heritages', () => {
    const src = read('src/scenes/Run.ts')
    const used = mechanicsReferencedBy(src)

    const puzzle = ['PuzzleObject', 'LockAndKey', 'GatedTrigger', 'TimeReverseMechanic']
    const platformer = ['PhysicsModifier', 'CheckpointProgression', 'PickupLoop']
    const roguelite = ['ProceduralRoomChain', 'RoomGraph', 'RouteMap', 'Difficulty']

    const hasPuzzle = puzzle.some(m => used.has(m))
    const hasPlatformer = platformer.some(m => used.has(m))
    const hasRoguelite = roguelite.some(m => used.has(m))

    const heritages = [hasPuzzle, hasPlatformer, hasRoguelite].filter(Boolean).length
    expect(heritages).toBeGreaterThanOrEqual(3)
  })

  it('main.ts boots the Run scene', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Run')
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
