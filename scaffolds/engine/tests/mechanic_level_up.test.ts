/**
 * Phase 3 — LevelUpProgression runtime smoke test.
 *
 * Verifies:
 * - Mechanic registers with the registry
 * - XP curve math (linear / quadratic / exponential) returns sensible values
 * - grantXP crosses thresholds and triggers level-up
 * - Level-up caps at max_level
 * - stat_gains apply, learn_at_level grants spells
 */

import { describe, it, expect } from 'vitest'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicInstance, LevelUpProgressionParams } from '../src/design/schema'

function makeStubGame(sceneEntities: unknown[] = []): any {
  return {
    sceneManager: {
      activeScene: () => ({ entities: sceneEntities }),
    },
    // No world_flags available — the mechanic wraps writeWorldFlag in
    // try/catch for this case.
  }
}

function makeLevelUpInstance(params: Partial<LevelUpProgressionParams> = {}): MechanicInstance {
  return {
    id: 'lup_test',
    type: 'LevelUpProgression',
    params: {
      xp_curve: 'linear',
      base_xp: 100,
      stat_gains: { hp: 5, atk: 1 },
      max_level: 10,
      ...params,
    } as LevelUpProgressionParams,
  }
}

describe('Phase 3 — LevelUpProgression runtime', () => {
  it('is registered in the mechanic registry', () => {
    expect(mechanicRegistry.has('LevelUpProgression')).toBe(true)
  })

  it('grantXP below threshold does not level up', () => {
    const rt = mechanicRegistry.create(makeLevelUpInstance(), makeStubGame())! as any
    rt.grantXP('player', 50)
    const p = rt.getProgress('player')
    expect(p?.level).toBe(1)
    expect(p?.xp).toBe(50)
  })

  it('grantXP crossing threshold levels up', () => {
    const rt = mechanicRegistry.create(makeLevelUpInstance(), makeStubGame())! as any
    rt.grantXP('player', 150)  // linear: needs 100 for level 2
    const p = rt.getProgress('player')
    expect(p?.level).toBe(2)
    expect(p?.xp).toBe(50)  // 150 - 100 carry-over
  })

  it('multiple level-ups in a single grant all fire', () => {
    const rt = mechanicRegistry.create(makeLevelUpInstance(), makeStubGame())! as any
    // Linear curve: level 2=100, level 3 requires 200 more (total 300)
    rt.grantXP('player', 500)
    const p = rt.getProgress('player')
    expect(p?.level).toBeGreaterThanOrEqual(3)
  })

  it('caps at max_level', () => {
    const rt = mechanicRegistry.create(
      makeLevelUpInstance({ max_level: 3 }),
      makeStubGame(),
    )! as any
    rt.grantXP('player', 99999)
    const p = rt.getProgress('player')
    expect(p?.level).toBe(3)
    expect(p?.xp).toBe(0)
  })

  it('quadratic curve scales sharper than linear', () => {
    const linear = mechanicRegistry.create(
      makeLevelUpInstance({ xp_curve: 'linear', base_xp: 100 }),
      makeStubGame(),
    )! as any
    const quad = mechanicRegistry.create(
      makeLevelUpInstance({ xp_curve: 'quadratic', base_xp: 100 }),
      makeStubGame(),
    )! as any
    // Same XP grant — quadratic should reach a lower level.
    linear.grantXP('p', 1000)
    quad.grantXP('p', 1000)
    expect(linear.getProgress('p').level).toBeGreaterThan(quad.getProgress('p').level)
  })

  it('applies stat_gains to the entity on level-up', () => {
    const entity = {
      id: 'player',
      properties: {
        Stats: { hp: 10, atk: 5 },
        Level: { current: 1, xp: 0 },
      },
    }
    const rt = mechanicRegistry.create(
      makeLevelUpInstance({ stat_gains: { hp: 5, atk: 2 } }),
      makeStubGame([entity]),
    )! as any
    rt.grantXP('player', 100)  // cross to level 2
    rt.update(0.016)  // process pending level-ups
    expect(entity.properties.Stats.hp).toBe(15)
    expect(entity.properties.Stats.atk).toBe(7)
  })

  it('grants learn_at_level spell when reached', () => {
    const entity = {
      id: 'player',
      properties: { Stats: {}, Spellbook: { spells: [] } },
    }
    const rt = mechanicRegistry.create(
      makeLevelUpInstance({
        learn_at_level: { 2: 'fireball' },
      }),
      makeStubGame([entity]),
    )! as any
    rt.grantXP('player', 100)  // level 2
    rt.update(0.016)
    expect((entity.properties.Spellbook as any).spells).toContain('fireball')
  })

  it('expose() returns per-target level / xp snapshot', () => {
    const rt = mechanicRegistry.create(makeLevelUpInstance(), makeStubGame())! as any
    rt.grantXP('player', 120)
    rt.grantXP('companion', 50)
    const snap = rt.expose()
    expect(snap['player.level']).toBeGreaterThanOrEqual(2)
    expect(snap['companion.level']).toBe(1)
    expect(snap['companion.xp']).toBe(50)
  })

  it('dispose clears state', () => {
    const rt = mechanicRegistry.create(makeLevelUpInstance(), makeStubGame())! as any
    rt.grantXP('player', 100)
    rt.dispose()
    expect(rt.getProgress('player')).toBeUndefined()
  })
})
