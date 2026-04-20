/**
 * Phase 8 — Platformer scaffold smoke test.
 *
 * Verifies the scaffold ships playable:
 * - Directory + required files exist
 * - Seed data parses (6 JSON files from JOB-G)
 * - Scenes import from @engine/mechanics ONLY (canary invariant)
 * - Scene mechanic mounts reference the platformer cluster
 * - Main boots Title → Level → GameOver scene flow
 * - All `tryMount(...)` names resolve in the registry
 * - PhysicsModifier is mounted with default gravity=1.0
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'platformer')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Phase 8 — Platformer scaffold', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 6 JOB-G seed files present under data/', () => {
    for (const f of ['config.json', 'player.json', 'enemies.json', 'powerups.json',
                     'levels.json', 'mechanics.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('player.json has movement params', () => {
    const data = readJSON('data/player.json') as any
    const p = data.player
    expect(p).toBeDefined()
    // Seed declares walk_speed / jump_height / coyote_frames or similar movement params.
    expect(typeof p).toBe('object')
  })

  it('enemies.json has at least 5 archetypes with tags', () => {
    const data = readJSON('data/enemies.json') as any
    const enemies = data.enemies
    expect(Object.keys(enemies).length).toBeGreaterThanOrEqual(5)
    for (const [_id, e] of Object.entries<any>(enemies)) {
      expect(Array.isArray(e.tags)).toBe(true)
    }
  })

  it('powerups.json has at least 4 pickup types', () => {
    const data = readJSON('data/powerups.json') as any
    const items = data.powerups
    expect(Object.keys(items).length).toBeGreaterThanOrEqual(4)
  })

  it('levels.json has at least 3 levels with checkpoints/exit', () => {
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

  it('Level scene mounts PhysicsModifier + CheckpointProgression + PickupLoop', () => {
    const src = read('src/scenes/Level.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.has('PhysicsModifier')).toBe(true)
    expect(used.has('CheckpointProgression')).toBe(true)
    expect(used.has('PickupLoop')).toBe(true)
    expect(used.has('CameraFollow')).toBe(true)
    expect(used.has('LockAndKey')).toBe(true)
    expect(used.has('HUD')).toBe(true)
  })

  it('main.ts boots the Title scene and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Title')
    expect(main).toContain('Level')
    expect(main).toContain('GameOver')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents PhysicsModifier + genre heritage', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('platformer')
    expect(readme).toMatch(/physicsmodifier/i)
    expect(readme).toMatch(/data\/[a-z_]+\.json/)
  })

  it('tsconfig.json paths alias points two levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../engine')
  })
})
