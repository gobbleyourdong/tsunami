/**
 * Phase 8 — FPS scaffold smoke test.
 *
 * Verifies the scaffold ships playable:
 * - Directory + required files exist
 * - Seed data parses (6 JSON files from JOB-H)
 * - Scenes import from @engine/mechanics ONLY (canary invariant)
 * - Scene mechanics reference the FPS cluster
 * - Main boots Title → Level → GameOver
 * - Every `tryMount(...)` name resolves in the registry
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'fps')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Phase 8 — FPS scaffold', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 6 JOB-H seed files present under data/', () => {
    for (const f of ['config.json', 'player.json', 'weapons.json', 'enemies.json',
                     'levels.json', 'mechanics.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('weapons.json has at least 6 weapons with projectile_kind', () => {
    const data = readJSON('data/weapons.json') as any
    const weapons = data.weapons
    expect(Object.keys(weapons).length).toBeGreaterThanOrEqual(6)
    const VALID = new Set(['hitscan', 'projectile', 'aoe'])
    for (const [_id, w] of Object.entries<any>(weapons)) {
      expect(VALID.has(w.projectile_kind)).toBe(true)
      expect(typeof w.damage).toBe('number')
    }
  })

  it('enemies.json has at least 4 archetypes with Health component + tags', () => {
    const data = readJSON('data/enemies.json') as any
    const enemies = data.enemies
    expect(Object.keys(enemies).length).toBeGreaterThanOrEqual(4)
    for (const [_id, e] of Object.entries<any>(enemies)) {
      // JOB-H seed declares HP via ComponentSpec (e.g. "Health(40)") in
      // `components`, not a top-level `hp` field — match the schema.
      expect(Array.isArray(e.components)).toBe(true)
      expect(e.components.some((c: string) => c.startsWith('Health('))).toBe(true)
      expect(Array.isArray(e.tags)).toBe(true)
    }
  })

  it('levels.json has at least 3 levels with rooms + doors', () => {
    const data = readJSON('data/levels.json') as any
    const levels = data.levels
    expect(Object.keys(levels).length).toBeGreaterThanOrEqual(3)
  })

  it('scenes import from @engine/mechanics only (CANARY invariant)', () => {
    for (const name of ['Title', 'Level', 'GameOver']) {
      const src = read(`src/scenes/${name}.ts`)
      expect(src).toContain("from '@engine/mechanics'")
      expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/(?:engine|mechanics|components)/)
    }
  })

  it('every mechanic name referenced in scenes is registered', () => {
    const all = new Set<string>()
    for (const name of ['Title', 'Level', 'GameOver']) {
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

  it('Level scene mounts BulletPattern + WaveSpawner + AttackFrames', () => {
    const src = read('src/scenes/Level.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.has('BulletPattern')).toBe(true)
    expect(used.has('WaveSpawner')).toBe(true)
    expect(used.has('AttackFrames')).toBe(true)
    expect(used.has('PickupLoop')).toBe(true)
    expect(used.has('LockAndKey')).toBe(true)
    expect(used.has('CameraFollow')).toBe(true)
    expect(used.has('HUD')).toBe(true)
  })

  it('main.ts boots Title and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Title')
    expect(main).toContain('Level')
    expect(main).toContain('GameOver')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the FPS cluster + genre heritage', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('fps')
    expect(readme).toMatch(/bulletpattern/i)
    expect(readme).toMatch(/wavespawner/i)
    expect(readme).toMatch(/data\/[a-z_]+\.json/)
  })

  it('tsconfig.json paths alias points two levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../engine')
  })
})
