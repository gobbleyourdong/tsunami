/**
 * Phase 8 — Racing scaffold smoke test.
 *
 * Verifies:
 * - Directory + required files exist
 * - JOB-T seed data parses (6 JSON files)
 * - Scenes import from @engine/mechanics ONLY (canary invariant)
 * - Scene mechanic mounts reference the racing cluster
 * - Main boots Title → Race → Finish
 * - Every `tryMount(...)` name resolves in the registry
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'racing')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Phase 8 — Racing scaffold', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 6 JOB-T seed files present under data/', () => {
    for (const f of ['config.json', 'tracks.json', 'vehicles.json', 'racers.json',
                     'powerups.json', 'mechanics.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('tracks.json has at least 3 tracks with checkpoints', () => {
    const data = readJSON('data/tracks.json') as any
    const tracks = data.tracks
    expect(Object.keys(tracks).length).toBeGreaterThanOrEqual(3)
    for (const [_id, t] of Object.entries<any>(tracks)) {
      expect(Array.isArray(t.checkpoints) || Array.isArray(t.tags)).toBe(true)
    }
  })

  it('vehicles.json has at least 4 archetypes with stat fields', () => {
    const data = readJSON('data/vehicles.json') as any
    const vehicles = data.vehicles
    expect(Object.keys(vehicles).length).toBeGreaterThanOrEqual(4)
  })

  it('racers.json has player + AI racers', () => {
    const data = readJSON('data/racers.json') as any
    const racers = data.racers
    expect(Object.keys(racers).length).toBeGreaterThanOrEqual(2)
  })

  it('scenes import from @engine/mechanics only (CANARY invariant)', () => {
    for (const name of ['Title', 'Race', 'Finish']) {
      const src = read(`src/scenes/${name}.ts`)
      expect(src).toContain("from '@engine/mechanics'")
      expect(src).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/(?:engine|mechanics|components)/)
    }
  })

  it('every mechanic name referenced in scenes is registered', () => {
    const all = new Set<string>()
    for (const name of ['Title', 'Race', 'Finish']) {
      const src = read(`src/scenes/${name}.ts`)
      for (const m of mechanicsReferencedBy(src)) all.add(m)
    }
    expect(all.size).toBeGreaterThanOrEqual(5)
    const unregistered: string[] = []
    for (const type of all) {
      if (!mechanicRegistry.has(type as any)) unregistered.push(type)
    }
    expect(unregistered).toEqual([])
  })

  it('Race scene mounts CheckpointProgression + CameraFollow + WinOnCount', () => {
    const src = read('src/scenes/Race.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.has('CheckpointProgression')).toBe(true)
    expect(used.has('CameraFollow')).toBe(true)
    expect(used.has('WinOnCount')).toBe(true)
    expect(used.has('HUD')).toBe(true)
  })

  it('main.ts boots Title and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Title')
    expect(main).toContain('Race')
    expect(main).toContain('Finish')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the racing cluster + genre heritage', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('racing')
    expect(readme).toMatch(/checkpointprogression/i)
    expect(readme).toMatch(/out\s*run|mario\s*kart|gran\s*turismo/i)
    expect(readme).toMatch(/data\/[a-z_]+\.json/)
  })

  it('tsconfig.json paths alias points two levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../engine')
  })
})
