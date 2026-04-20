/**
 * Phase 3 — ATBCombat runtime smoke test.
 *
 * Verifies:
 * - Mechanic registers with the registry
 * - ATB meters fill over time proportional to speed × atb_speed
 * - queueCommand only fires when the actor's meter reaches 1.0
 * - Attack applies damage, wipes out target, flips outcome to victory
 * - Enemy auto-attack fires when enemy meter fills
 * - Row swap honored only when can_swap_rows=true
 * - Run sets outcome=fled
 */

import { describe, it, expect } from 'vitest'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicInstance, ATBCombatParams } from '../src/design/schema'

function makeStubGame(): any {
  return { sceneManager: { activeScene: () => ({ entities: [] }) } }
}

function makeInstance(params: Partial<ATBCombatParams> = {}): MechanicInstance {
  return {
    id: 'atb_test',
    type: 'ATBCombat',
    params: {
      party_size: 3,
      atb_speed: 1.0,
      command_menu: ['attack', 'magic', 'item', 'defend'],
      can_swap_rows: false,
      ...params,
    } as ATBCombatParams,
  }
}

function makeCombatants() {
  return {
    party: [
      { id: 'hero', team: 'party' as const, hp: 100, hp_max: 100, speed: 10, atb: 0, ko: false },
      { id: 'mage', team: 'party' as const, hp:  60, hp_max:  60, speed:  8, atb: 0, ko: false },
    ],
    enemies: [
      { id: 'slime', team: 'enemy' as const, hp: 20, hp_max: 20, speed: 4, atb: 0, ko: false },
    ],
  }
}

describe('Phase 3 — ATBCombat runtime', () => {
  it('is registered in the mechanic registry', () => {
    expect(mechanicRegistry.has('ATBCombat')).toBe(true)
  })

  it('startCombat seeds combatants with atb=0', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    expect(rt.getMeter('hero')).toBe(0)
    expect(rt.getOutcome()).toBe('ongoing')
  })

  it('update fills ATB meters proportional to speed', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    rt.update(1.0)
    // hero speed 10 > mage speed 8 > slime speed 4
    expect(rt.getMeter('hero')).toBeGreaterThan(rt.getMeter('mage'))
    expect(rt.getMeter('mage')).toBeGreaterThan(rt.getMeter('slime'))
  })

  it('atb_speed scales fill rate globally', () => {
    const slow = mechanicRegistry.create(makeInstance({ atb_speed: 1.0 }), makeStubGame())! as any
    const fast = mechanicRegistry.create(makeInstance({ atb_speed: 4.0 }), makeStubGame())! as any
    const { party, enemies } = makeCombatants()
    slow.startCombat(party, enemies)
    fast.startCombat(party, enemies)
    slow.update(1.0)
    fast.update(1.0)
    expect(fast.getMeter('hero')).toBeCloseTo(slow.getMeter('hero') * 4, 4)
  })

  it('queueCommand rejects commands not in menu', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ command_menu: ['attack', 'defend'] }), makeStubGame(),
    )! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    expect(rt.queueCommand('hero', 'attack', 'slime')).toBe(true)
    expect(rt.queueCommand('hero', 'magic', 'slime')).toBe(false)
  })

  it('queued command does NOT fire until meter reaches 1.0', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    rt.queueCommand('hero', 'attack', 'slime')
    rt.update(0.5)  // hero meter ~0.05 at speed 10 × 0.01 × 0.5 = 0.05
    expect(rt.getCombatant('slime')?.hp).toBe(20)  // not yet hit
  })

  it('queued command fires and resets meter when ATB fills', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ atb_speed: 100.0 }), makeStubGame(),
    )! as any
    const { party } = makeCombatants()
    const weakEnemy = [
      { id: 'bug', team: 'enemy' as const, hp: 1, hp_max: 1, speed: 1, atb: 0, ko: false },
    ]
    rt.startCombat(party, weakEnemy)
    rt.queueCommand('hero', 'attack', 'bug')
    // atb_speed 100 × speed 10 × ATB_FILL_BASE 0.01 × dt 1.0 = 10.0 → capped to 1.0
    rt.update(1.0)
    expect(rt.getCombatant('bug')?.ko).toBe(true)
    expect(rt.getOutcome()).toBe('victory')
  })

  it('enemy auto-attacks when its meter fills', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ atb_speed: 100.0 }), makeStubGame(),
    )! as any
    const party = [
      { id: 'hero', team: 'party' as const, hp: 5, hp_max: 5, speed: 1, atb: 0, ko: false },
    ]
    const enemies = [
      { id: 'troll', team: 'enemy' as const, hp: 500, hp_max: 500, speed: 30, atb: 0, ko: false },
    ]
    rt.startCombat(party, enemies)
    // No player command queued — enemy should auto-attack when its meter fills.
    rt.update(1.0)
    expect(rt.getCombatant('hero')?.hp).toBeLessThan(5)
  })

  it('setRow rejected when can_swap_rows=false', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    expect(rt.setRow('hero', 'back')).toBe(false)
  })

  it('setRow accepted when can_swap_rows=true', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ can_swap_rows: true }), makeStubGame(),
    )! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    expect(rt.setRow('hero', 'back')).toBe(true)
    expect(rt.getCombatant('hero')?.row).toBe('back')
  })

  it('run sets outcome=fled when fired', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ atb_speed: 100.0 }), makeStubGame(),
    )! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    rt.queueCommand('hero', 'run')
    rt.update(1.0)
    expect(rt.getOutcome()).toBe('fled')
  })

  it('expose() returns meters + ready list + alive counts', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    rt.update(10.0)  // let some meters fill
    const snap = rt.expose()
    expect(snap.outcome).toBe('ongoing')
    expect(Object.keys(snap.atb_meters as Record<string, unknown>)).toContain('hero')
    expect(snap.party_alive).toBe(2)
    expect(snap.enemy_alive).toBe(1)
  })

  it('dispose clears state', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    const { party, enemies } = makeCombatants()
    rt.startCombat(party, enemies)
    rt.dispose()
    expect(rt.getMeter('hero')).toBe(0)
    expect(rt.getCombatant('hero')).toBeUndefined()
  })
})
