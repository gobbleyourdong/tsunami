/**
 * Cross-genre canary — bullet_hell_rpg.
 *
 * Proves the scaffold composes from @engine/mechanics alone. Any
 * `tryMount('X', ...)` whose name isn't in the registry, or any
 * import that reaches into ../../mechanics/ or ../../components/
 * counts as architecture drift.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'cross', 'bullet_hell_rpg')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Cross-genre canary — bullet_hell_rpg', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 6 data files present', () => {
    for (const f of ['config.json', 'player.json', 'enemies.json', 'waves.json',
                     'bosses.json', 'equipment.json', 'progression.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('enemies.json has >= 5 archetypes with BulletPattern params', () => {
    const data = readJSON('data/enemies.json')
    const enemies = data.enemies
    expect(Object.keys(enemies).length).toBeGreaterThanOrEqual(5)
    for (const e of Object.values<any>(enemies)) {
      expect(e.pattern).toBeDefined()
      expect(typeof e.pattern.bullets_per_burst).toBe('number')
      expect(typeof e.pattern.bullet_speed).toBe('number')
      expect(typeof e.pattern.interval_ms).toBe('number')
    }
  })

  it('waves.json schedules at least 5 waves', () => {
    const w = readJSON('data/waves.json')
    expect(Array.isArray(w.waves)).toBe(true)
    expect(w.waves.length).toBeGreaterThanOrEqual(5)
    for (const wave of w.waves) {
      expect(typeof wave.at_sec).toBe('number')
      expect(typeof wave.archetype).toBe('string')
      expect(typeof wave.count).toBe('number')
    }
  })

  it('bosses.json has phases that escalate on hp', () => {
    const b = readJSON('data/bosses.json')
    const boss = b.bosses.the_archon
    expect(Array.isArray(boss.phases)).toBe(true)
    expect(boss.phases.length).toBeGreaterThanOrEqual(3)
    const hps = boss.phases.map((p: any) => p.at_hp_pct)
    for (let i = 1; i < hps.length; i++) expect(hps[i]).toBeLessThan(hps[i - 1])
  })

  it('equipment.json has items across at least 3 slots', () => {
    const eq = readJSON('data/equipment.json').equipment
    const slots = new Set(Object.values<any>(eq).map(i => i.slot))
    expect(slots.size).toBeGreaterThanOrEqual(3)
  })

  it('progression.json has xp_curve + level_rewards + status_effects', () => {
    const p = readJSON('data/progression.json').progression
    expect(Array.isArray(p.xp_curve)).toBe(true)
    expect(p.xp_curve.length).toBeGreaterThanOrEqual(5)
    expect(Array.isArray(p.level_rewards)).toBe(true)
    expect(typeof p.status_effects).toBe('object')
  })

  it('Run scene imports from @engine/mechanics only (CANARY)', () => {
    const run = read('src/scenes/Run.ts')
    expect(run).toContain("from '@engine/mechanics'")
    expect(run).not.toMatch(/from\s+['"]\.\.\/\.\.\/mechanics/)
    expect(run).not.toMatch(/from\s+['"]\.\.\/\.\.\/components/)
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

  it('Run composes mechanics from 3+ genre heritages (proves cross-genre)', () => {
    const src = read('src/scenes/Run.ts')
    const used = mechanicsReferencedBy(src)

    const bulletHell = ['BulletPattern', 'WaveSpawner', 'BossPhases', 'ScoreCombos']
    const rpg = ['LevelUpProgression', 'EquipmentLoadout', 'StatusStack', 'PartyComposition']
    const fighting = ['AttackFrames', 'ComboAttacks', 'BossPhases']
    const action = ['CameraFollow', 'CheckpointProgression', 'RoomGraph']

    const hasBulletHell = bulletHell.some(m => used.has(m))
    const hasRPG = rpg.some(m => used.has(m))
    const hasFighting = fighting.some(m => used.has(m))
    const hasAction = action.some(m => used.has(m))

    const heritages = [hasBulletHell, hasRPG, hasFighting, hasAction].filter(Boolean).length
    expect(heritages).toBeGreaterThanOrEqual(3)
  })

  it('main.ts boots the Run scene', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Run')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the cross-genre role + heritage mix', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('cross-genre')
    expect(readme.toLowerCase()).toContain('heritage')
    expect(readme.toLowerCase()).toContain('canary')
  })

  it('tsconfig.json engine path alias goes three levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../../engine')
  })
})
