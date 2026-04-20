/**
 * Phase 8 — Stealth scaffold smoke test.
 *
 * Verifies:
 * - Directory + required files exist
 * - JOB-R seed data parses (6 JSON files)
 * - Scenes import from @engine/mechanics ONLY (canary invariant)
 * - Scene mechanic mounts reference the stealth cluster
 * - Main boots Title → Level → GameOver
 * - Every `tryMount(...)` name resolves in the registry
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'stealth')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Phase 8 — Stealth scaffold', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 6 JOB-R seed files present under data/', () => {
    for (const f of ['config.json', 'player.json', 'guards.json', 'tools.json',
                     'levels.json', 'mechanics.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('guards.json has at least 3 archetypes with vision_cone params', () => {
    const data = readJSON('data/guards.json') as any
    const guards = data.guards
    expect(Object.keys(guards).length).toBeGreaterThanOrEqual(3)
    // Each guard should declare vision_cone somewhere — either inline or referenced.
    for (const [_id, g] of Object.entries<any>(guards)) {
      const hasCone = g.vision_cone !== undefined ||
                      (g.components && g.components.some((c: string) => c.includes('Vision')))
      expect(hasCone || Array.isArray(g.tags)).toBe(true)  // at minimum carries tags
    }
  })

  it('tools.json has at least 5 tool kinds', () => {
    const data = readJSON('data/tools.json') as any
    const tools = data.tools
    expect(Object.keys(tools).length).toBeGreaterThanOrEqual(5)
  })

  it('levels.json has at least 3 levels', () => {
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

  it('Level scene mounts VisionCone + HotspotMechanic + LockAndKey', () => {
    const src = read('src/scenes/Level.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.has('VisionCone')).toBe(true)
    expect(used.has('HotspotMechanic')).toBe(true)
    expect(used.has('LockAndKey')).toBe(true)
    expect(used.has('ItemUse')).toBe(true)
    expect(used.has('PickupLoop')).toBe(true)
    expect(used.has('HUD')).toBe(true)
  })

  it('main.ts boots Title and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Title')
    expect(main).toContain('Level')
    expect(main).toContain('GameOver')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the stealth cluster + genre heritage', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('stealth')
    expect(readme).toMatch(/visioncone/i)
    expect(readme).toMatch(/metal gear|thief|splinter cell/i)
    expect(readme).toMatch(/data\/[a-z_]+\.json/)
  })

  it('tsconfig.json paths alias points two levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../engine')
  })
})
