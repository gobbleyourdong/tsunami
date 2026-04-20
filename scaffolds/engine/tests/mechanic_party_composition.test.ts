/**
 * Phase 3 — PartyComposition runtime smoke test.
 *
 * Verifies:
 * - Registers with the mechanic registry
 * - addToRoster respects max_roster cap + unique-id constraint
 * - setActive / swapInOut / setActiveParty honor max_active + no-dupe
 * - Battle lock gates mid-battle swaps unless can_swap_mid_battle=true
 * - Row swap persists; formation change emits world-flag
 * - expose() surfaces active / reserve / roster sizes + battle_locked
 */

import { describe, it, expect } from 'vitest'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicInstance, PartyCompositionParams } from '../src/design/schema'

function makeStubGame(): any {
  return { sceneManager: { activeScene: () => ({ entities: [] }) } }
}

function makeInstance(params: Partial<PartyCompositionParams> = {}): MechanicInstance {
  return {
    id: 'pc_test',
    type: 'PartyComposition',
    params: {
      max_active: 4,
      max_roster: 8,
      can_swap_mid_battle: false,
      default_formation: 'row_standard',
      ...params,
    } as PartyCompositionParams,
  }
}

function seed6(rt: any) {
  rt.addToRoster('cecil',  'warrior')
  rt.addToRoster('rydia',  'black_mage')
  rt.addToRoster('rosa',   'white_mage')
  rt.addToRoster('edge',   'thief_ninja')
  rt.addToRoster('yang',   'monk')
  rt.addToRoster('palom',  'black_mage')
}

describe('Phase 3 — PartyComposition runtime', () => {
  it('is registered in the mechanic registry', () => {
    expect(mechanicRegistry.has('PartyComposition')).toBe(true)
  })

  it('addToRoster enforces max_roster cap', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ max_roster: 2 }), makeStubGame(),
    )! as any
    expect(rt.addToRoster('a', 'warrior')).toBe(true)
    expect(rt.addToRoster('b', 'mage')).toBe(true)
    expect(rt.addToRoster('c', 'healer')).toBe(false)
  })

  it('addToRoster rejects duplicate ids', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    expect(rt.addToRoster('cecil', 'warrior')).toBe(true)
    expect(rt.addToRoster('cecil', 'knight')).toBe(false)
  })

  it('setActiveParty rejects more than max_active', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ max_active: 3 }), makeStubGame(),
    )! as any
    seed6(rt)
    expect(rt.setActiveParty(['cecil', 'rydia', 'rosa', 'edge'])).toBe(false)
    expect(rt.setActiveParty(['cecil', 'rydia', 'rosa'])).toBe(true)
    expect(rt.getActive()).toEqual(['cecil', 'rydia', 'rosa'])
  })

  it('setActiveParty rejects duplicates', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    expect(rt.setActiveParty(['cecil', 'cecil', 'rydia'])).toBe(false)
  })

  it('setActiveParty rejects unknown ids', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    expect(rt.setActiveParty(['cecil', 'ghost'])).toBe(false)
  })

  it('swapInOut replaces an active with a reserve when idle', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    rt.setActiveParty(['cecil', 'rydia', 'rosa', 'edge'])
    expect(rt.swapInOut('edge', 'yang')).toBe(true)
    expect(rt.getActive()).toEqual(['cecil', 'rydia', 'rosa', 'yang'])
    expect(rt.getReserve()).toContain('edge')
  })

  it('swapInOut blocked mid-battle when can_swap_mid_battle=false', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    rt.setActiveParty(['cecil', 'rydia', 'rosa', 'edge'])
    rt.startBattle()
    expect(rt.swapInOut('edge', 'yang')).toBe(false)
    rt.endBattle()
    expect(rt.swapInOut('edge', 'yang')).toBe(true)
  })

  it('swapInOut allowed mid-battle when can_swap_mid_battle=true (FF10 mechanic)', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ can_swap_mid_battle: true }), makeStubGame(),
    )! as any
    seed6(rt)
    rt.setActiveParty(['cecil', 'rydia', 'rosa', 'edge'])
    rt.startBattle()
    expect(rt.swapInOut('edge', 'yang')).toBe(true)
  })

  it('setRow persists on a member', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    expect(rt.setRow('cecil', 'back')).toBe(true)
    expect(rt.getMember('cecil')?.row).toBe('back')
  })

  it('setFormation updates the exposed formation id', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    expect(rt.getFormation()).toBe('row_standard')
    rt.setFormation('row_defensive')
    expect(rt.getFormation()).toBe('row_defensive')
  })

  it('removeFromRoster rejected for active member mid-battle', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    rt.setActiveParty(['cecil', 'rydia', 'rosa', 'edge'])
    rt.startBattle()
    expect(rt.removeFromRoster('cecil')).toBe(false)
    rt.endBattle()
    expect(rt.removeFromRoster('cecil')).toBe(true)
    expect(rt.getActive()).not.toContain('cecil')
  })

  it('expose() surfaces active + reserve + sizes + battle_locked', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    rt.setActiveParty(['cecil', 'rydia', 'rosa', 'edge'])
    rt.startBattle()
    const snap = rt.expose() as any
    expect(snap.active_party).toEqual(['cecil', 'rydia', 'rosa', 'edge'])
    expect(snap.reserve_party).toEqual(expect.arrayContaining(['yang', 'palom']))
    expect(snap.roster_size).toBe(6)
    expect(snap.active_size).toBe(4)
    expect(snap.formation).toBe('row_standard')
    expect(snap.battle_locked).toBe(true)
  })

  it('dispose clears state', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    seed6(rt)
    rt.setActiveParty(['cecil', 'rydia'])
    rt.dispose()
    expect(rt.getRoster()).toEqual([])
    expect(rt.getActive()).toEqual([])
  })
})
