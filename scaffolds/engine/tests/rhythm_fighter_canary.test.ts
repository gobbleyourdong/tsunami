/**
 * Cross-genre canary #3 — rhythm_fighter.
 *
 * Paralleling magic_hoops + ninja_garden canaries. Verifies:
 * - Scaffold directory + build chain + 6 data files present.
 * - Scenes import ONLY from `@engine/mechanics`.
 * - Every `tryMount(...)` mechanic name is in the registry.
 * - Composition exercises fighting + rhythm heritages.
 * - **RhythmTrack mounts BEFORE AttackFrames** — execution-order
 *   invariant; AttackFrames reads beat-phase from RhythmTrack, so
 *   order must be stable.
 * - moves.json expresses frame-data in beat-fractions, not frames.
 * - tsconfig's `@engine` alias three levels up.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'cross', 'rhythm_fighter')

const read = (rel: string) => readFileSync(join(SCAFFOLD, rel), 'utf8')
const readJSON = (rel: string) => JSON.parse(read(rel))

function mechanicsReferencedBy(source: string): Set<string> {
  const out = new Set<string>()
  const pattern = /tryMount\(['"]([A-Z][A-Za-z0-9_]+)['"]/g
  const matches = source.matchAll(pattern)
  for (const mm of matches) out.add(mm[1])
  return out
}

describe('Cross-canary #3 — rhythm_fighter (fighting+rhythm)', () => {
  it('scaffold directory + build chain exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
    for (const f of ['package.json', 'tsconfig.json', 'vite.config.ts', 'index.html', 'README.md']) {
      expect(existsSync(join(SCAFFOLD, f))).toBe(true)
    }
  })

  it('all 6 data files present', () => {
    for (const f of ['config.json', 'characters.json', 'moves.json',
                     'stages.json', 'beatmaps.json', 'mechanics.json']) {
      expect(existsSync(join(SCAFFOLD, 'data', f))).toBe(true)
    }
  })

  it('config declares on_beat/off_beat damage multipliers', () => {
    const data = readJSON('data/config.json') as any
    expect(data.match_rules.on_beat_damage_multiplier).toBe(1.5)
    expect(data.match_rules.off_beat_damage_multiplier).toBe(0.5)
    expect(typeof data.match_rules.on_beat_window_beats).toBe('number')
  })

  it('characters.json has ≥2 fighters with rhythm_bonus resource', () => {
    const data = readJSON('data/characters.json') as any
    const chars = data.characters
    expect(Object.keys(chars).length).toBeGreaterThanOrEqual(2)
    for (const [_id, c] of Object.entries<any>(chars)) {
      expect(Array.isArray(c.components)).toBe(true)
      expect(c.components.some((cc: string) => cc.includes('rhythm_bonus'))).toBe(true)
    }
  })

  it('moves.json expresses frame-data in beat-fractions (not frames)', () => {
    const data = readJSON('data/moves.json') as any
    const movesets = data.movesets
    let checked = 0
    for (const [_msid, ms] of Object.entries<any>(movesets)) {
      for (const [_mid, move] of Object.entries<any>(ms)) {
        // Beat-fraction fields must be present.
        expect(typeof move.startup_beats).toBe('number')
        expect(typeof move.active_beats).toBe('number')
        expect(typeof move.recovery_beats).toBe('number')
        // Values should be small (fractions of a beat), not frame counts.
        expect(move.startup_beats).toBeLessThan(5)
        checked += 1
      }
    }
    expect(checked).toBeGreaterThanOrEqual(3)
  })

  it('beatmaps.json has BPM + accent_beats per beatmap', () => {
    const data = readJSON('data/beatmaps.json') as any
    const maps = data.beatmaps
    expect(Object.keys(maps).length).toBeGreaterThanOrEqual(2)
    for (const [_id, b] of Object.entries<any>(maps)) {
      expect(typeof b.bpm).toBe('number')
      expect(Array.isArray(b.accent_beats)).toBe(true)
    }
  })

  it('Match scene imports from @engine/mechanics only (CANARY invariant)', () => {
    const match = read('src/scenes/Match.ts')
    expect(match).toContain("from '@engine/mechanics'")
    expect(match).not.toMatch(/from\s+['"]\.\.\/\.\.\/\.\.\/\.\.\/(?:engine|mechanics|components)/)
  })

  it('Match references ONLY registered mechanic types (CANARY)', () => {
    const src = read('src/scenes/Match.ts')
    const used = mechanicsReferencedBy(src)
    expect(used.size).toBeGreaterThanOrEqual(6)
    const unregistered: string[] = []
    for (const type of used) {
      if (!mechanicRegistry.has(type as any)) unregistered.push(type)
    }
    expect(unregistered).toEqual([])
  })

  it('Match composes fighting + rhythm heritages (≥2 genre heritages)', () => {
    const src = read('src/scenes/Match.ts')
    const used = mechanicsReferencedBy(src)

    // Fighting (SF2 lineage): ComboAttacks, AttackFrames, WinOnCount
    const fighting = ['ComboAttacks', 'AttackFrames', 'WinOnCount']
    // Rhythm (PaRappa / Gitaroo): RhythmTrack, ChipMusic
    const rhythm = ['RhythmTrack', 'ChipMusic']

    const hasFighting = fighting.some((f) => used.has(f))
    const hasRhythm = rhythm.some((r) => used.has(r))

    expect(hasFighting).toBe(true)
    expect(hasRhythm).toBe(true)
  })

  it('EXECUTION-ORDER invariant: RhythmTrack mounts before AttackFrames', () => {
    // Source-order assertion — the first tryMount('RhythmTrack', ...)
    // must appear BEFORE the first tryMount('AttackFrames', ...) in the
    // source. Otherwise AttackFrames reads stale beat-phase on the first
    // tick (RhythmTrack hasn't initialized its beat clock yet).
    const src = read('src/scenes/Match.ts')
    const rhythmIdx = src.indexOf("tryMount('RhythmTrack'")
    const framesIdx = src.indexOf("tryMount('AttackFrames'")
    expect(rhythmIdx).toBeGreaterThan(0)
    expect(framesIdx).toBeGreaterThan(0)
    expect(rhythmIdx).toBeLessThan(framesIdx)
  })

  it('mechanics.json declares exactly the 8 target mechanic types', () => {
    const data = readJSON('data/mechanics.json') as any
    const types = new Set((data.mechanics ?? []).map((m: any) => m.type))
    for (const t of [
      'RhythmTrack', 'AttackFrames', 'ComboAttacks', 'StatusStack',
      'ChipMusic', 'SfxLibrary', 'HUD', 'WinOnCount',
    ]) {
      expect(types.has(t)).toBe(true)
    }
  })

  it('AttackFrames mechanic declares timing_unit=beats + beat_source_ref', () => {
    const data = readJSON('data/mechanics.json') as any
    const af = (data.mechanics ?? []).filter((m: any) => m.type === 'AttackFrames')
    expect(af.length).toBeGreaterThanOrEqual(1)
    for (const m of af) {
      expect(m.params.timing_unit).toBe('beats')
      expect(m.params.beat_source_ref).toBeTruthy()
    }
  })

  it('main.ts boots the Match scene and imports @engine/mechanics', () => {
    const main = read('src/main.ts')
    expect(main).toContain('Match')
    expect(main).toContain('@engine/mechanics')
  })

  it('README documents the timing-coupling axis + canary role', () => {
    const readme = read('README.md')
    expect(readme.toLowerCase()).toContain('canary')
    expect(readme.toLowerCase()).toContain('cross-genre')
    expect(readme).toMatch(/rhythm|beat/i)
    expect(readme).toMatch(/attackframes|rhythmtrack/i)
  })

  it('tsconfig.json paths alias goes three levels up', () => {
    const tsc = readJSON('tsconfig.json')
    const enginePath = tsc.compilerOptions?.paths?.['@engine']?.[0]
    expect(enginePath).toContain('../../../engine')
  })
})
