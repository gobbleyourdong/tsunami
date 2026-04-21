/**
 * Phase 8 — Beat-em-up scaffold smoke test.
 *
 * Genre scaffold #9. Verifies the scaffold ships playable with sister
 * JOB-INT-7 seed data:
 * - Directory + required files exist
 * - All 9 seed JSON files present + parse
 * - Scenes import from @engine/mechanics ONLY (canary invariant)
 * - Scene mechanic mounts reference the beat-em-up cluster
 * - Main boots Title → Stage → GameOver
 * - Every `tryMount(...)` name resolves in the registry
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'beat_em_up')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Phase 8 — Beat-em-up scaffold', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 9 JOB-INT-7 seed files present under data/', () => {
    for (const f of ['config.json', 'characters.json', 'enemies.json',
                     'stages.json', 'moves.json', 'pickups.json',
                     'rules.json', 'mechanics.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('characters.json has 3 playable brawlers', () => {
    const data = readJSON('data/characters.json') as any
    const chars = data.characters
    expect(Object.keys(chars).length).toBeGreaterThanOrEqual(3)
  })

  it('enemies.json has ≥5 archetypes', () => {
    const data = readJSON('data/enemies.json') as any
    expect(Object.keys(data.enemies).length).toBeGreaterThanOrEqual(5)
  })

  it('stages.json has ≥4 stages with waves', () => {
    const data = readJSON('data/stages.json') as any
    expect(Object.keys(data.stages).length).toBeGreaterThanOrEqual(4)
  })

  it('scenes import from @engine/mechanics only (CANARY invariant)', () => {
    for (const name of ['Title', 'Stage', 'GameOver']) {
      const src = read(`src/scenes/${name}.ts`)
      expect(src).toContain("from '@engine/mechanics'")
      expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/(?:engine|mechanics|components)/)
    }
  })

  it('every mechanic name referenced in scenes is registered', () => {
    const all = new Set<string>()
    for (const name of ['Title', 'Stage', 'GameOver']) {
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

  it('Stage scene mounts ComboAttacks + WaveSpawner + AttackFrames', () => {
    const src = read('src/scenes/Stage.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.has('ComboAttacks')).toBe(true)
    expect(used.has('WaveSpawner')).toBe(true)
    expect(used.has('AttackFrames')).toBe(true)
    expect(used.has('CameraFollow')).toBe(true)
    expect(used.has('PickupLoop')).toBe(true)
    expect(used.has('HUD')).toBe(true)
  })

  it('main.ts boots Title and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Title')
    expect(main).toContain('Stage')
    expect(main).toContain('GameOver')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the beat-em-up cluster + genre heritage', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('beat-em-up')
    expect(readme).toMatch(/final fight|streets of rage|turtles/i)
    expect(readme).toMatch(/data\/[a-z_]+\.json/)
  })

  it('tsconfig.json paths alias points two levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../engine')
  })
})
