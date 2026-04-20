/**
 * Phase 7 — cross-genre canary test.
 *
 * Verifies that the magic-hoops scaffold composes from @engine/mechanics
 * ALONE. Any reference to a mechanic type not in the registered set is
 * an architecture failure — the abstractions are leaking genre bias and
 * need fixing at Layer 1/2.
 *
 * This is the most important test in the whole framework build. If it
 * passes, we know genre scaffolds compose cleanly; if it fails, we
 * have concrete drift to fix.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'cross', 'magic_hoops')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

/** Pull every `tryMount('X', ...)` mechanic-name from scene source. */
function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) {
    out.add(mm[1])
  }
  return out
}

describe('Phase 7 — cross-genre canary (magic-hoops)', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 4 data files present', () => {
    for (const f of ['config.json', 'rules.json', 'arena.json', 'characters.json', 'spells.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('characters.json has 2 wizards across 2 teams (1v1 minimum)', () => {
    const data = readJSON('data/characters.json')
    const chars = data.characters
    const ids = Object.keys(chars)
    expect(ids.length).toBeGreaterThanOrEqual(2)
    const teams = new Set(Object.values<any>(chars).map((c) => c.team_id))
    expect(teams.size).toBeGreaterThanOrEqual(2)
  })

  it('characters use components from the canonical vocabulary', () => {
    const chars = readJSON('data/characters.json').characters
    for (const [id, c] of Object.entries<any>(chars)) {
      expect(Array.isArray(c.components)).toBe(true)
      expect(c.components.length).toBeGreaterThan(0)
      const healthComp = c.components.find((cc: string) => cc.startsWith('Health('))
      expect(healthComp).toBeDefined()
    }
  })

  it('spells.json has at least 4 spells with canonical input notation', () => {
    const data = readJSON('data/spells.json')
    const spells = data.spells
    expect(Object.keys(spells).length).toBeGreaterThanOrEqual(4)
    for (const [id, s] of Object.entries<any>(spells)) {
      expect(typeof s.mana_cost).toBe('number')
      expect(typeof s.cooldown_sec).toBe('number')
    }
  })

  it('arena.json has 2 goals + ball + rect boundary', () => {
    const a = readJSON('data/arena.json')
    expect(a.goals.length).toBe(2)
    expect(a.goals[0].team_id).not.toBe(a.goals[1].team_id)
    expect(a.ball).toBeDefined()
    expect(a.boundary.kind).toBe('rect')
  })

  it('rules.json declares score_vs_clock composite format', () => {
    const r = readJSON('data/rules.json')
    expect(r.match_format).toBe('score_vs_clock')
    expect(r.win_condition).toBe('highest_score_at_clock_end')
    expect(r.teams).toBe(2)
    expect(typeof r.clock_sec).toBe('number')
  })

  it('Match scene imports from @engine/mechanics only (CANARY)', () => {
    const match = read('src/scenes/Match.ts')
    // Scene must ONLY pull mechanics from @engine/mechanics — any
    // relative import into parent mechanics dir = architecture drift.
    expect(match).toContain("from '@engine/mechanics'")
    expect(match).not.toMatch(/from\s+['"]\.\.\/\.\.\/mechanics/)
    expect(match).not.toMatch(/from\s+['"]\.\.\/\.\.\/components/)
  })

  it('Match references ONLY registered mechanic types (CANARY)', () => {
    const src = read('src/scenes/Match.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.size).toBeGreaterThanOrEqual(4)
    // Every name must be in the registry.
    const unregistered: string[] = []
    for (const type of used) {
      if (!mechanicRegistry.has(type as any)) {
        unregistered.push(type)
      }
    }
    expect(unregistered).toEqual([])
  })

  it('Match composes mechanics from 3+ genre heritages (proves cross-genre)', () => {
    const src = read('src/scenes/Match.ts')
    const used = mechanicsReferencedBy(src)

    const fighting = ['ComboAttacks', 'AttackFrames', 'BossPhases']
    const action = ['CameraFollow', 'RoomGraph', 'CheckpointProgression']
    const scoring = ['WinOnCount', 'ScoreCombos']

    const hasFighting = fighting.some((f) => used.has(f))
    const hasAction = action.some((a) => used.has(a))
    const hasScoring = scoring.some((s) => used.has(s))

    const heritages = [hasFighting, hasAction, hasScoring].filter(Boolean).length
    expect(heritages).toBeGreaterThanOrEqual(3)
  })

  it('main.ts boots the Match scene', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Match')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the canary role', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('canary')
    expect(readme.toLowerCase()).toContain('cross-genre')
    expect(readme).toMatch(/architecture/i)
  })

  it('tsconfig.json paths alias goes three levels up (nested dir)', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../../engine')
  })
})
