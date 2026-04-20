/**
 * Phase 3 residual — RoleAssignment runtime smoke test.
 *
 * Verifies:
 * - Registers with the mechanic registry
 * - Initial roles declared, initial_assignments applied on init
 * - assign / revoke / swap honor single-holder vs allow_multi_role
 * - assignable_tag filters entities lacking the tag
 * - holdersOf / rolesHeldBy return current state
 * - expose() surfaces role_assignments dict
 */

import { describe, it, expect } from 'vitest'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicInstance, RoleAssignmentParams } from '../src/design/schema'

function makeStubGame(entities: unknown[] = []): any {
  return { sceneManager: { activeScene: () => ({ entities }) } }
}

function makeInstance(params: Partial<RoleAssignmentParams> = {}): MechanicInstance {
  return {
    id: 'ra_test',
    type: 'RoleAssignment',
    params: {
      roles: ['player_controlled', 'leader', 'healer', 'scout'],
      ...params,
    } as RoleAssignmentParams,
  }
}

describe('Phase 3 — RoleAssignment runtime', () => {
  it('is registered in the mechanic registry', () => {
    expect(mechanicRegistry.has('RoleAssignment')).toBe(true)
  })

  it('declared roles are listed after init', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    expect(rt.listRoles()).toEqual(['player_controlled', 'leader', 'healer', 'scout'])
  })

  it('initial_assignments apply on init', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ initial_assignments: { player_controlled: 'erik', leader: 'baleog' } }),
      makeStubGame(),
    )! as any
    expect(rt.holdersOf('player_controlled')).toEqual(['erik'])
    expect(rt.holdersOf('leader')).toEqual(['baleog'])
  })

  it('assign rejects unknown role', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    expect(rt.assign('wizard', 'erik')).toBe(false)
  })

  it('assign steals role from prior holder when allow_multi_role=false', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.assign('player_controlled', 'erik')
    rt.assign('player_controlled', 'baleog')  // should steal
    expect(rt.holdersOf('player_controlled')).toEqual(['baleog'])
  })

  it('assign adds without stealing when allow_multi_role=true', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ allow_multi_role: true }), makeStubGame(),
    )! as any
    rt.assign('leader', 'erik')
    rt.assign('leader', 'baleog')  // additive
    const holders = rt.holdersOf('leader').sort()
    expect(holders).toEqual(['baleog', 'erik'])
  })

  it('revoke strips a specific entity', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ allow_multi_role: true }), makeStubGame(),
    )! as any
    rt.assign('leader', 'erik')
    rt.assign('leader', 'baleog')
    expect(rt.revoke('leader', 'erik')).toBe(true)
    expect(rt.holdersOf('leader')).toEqual(['baleog'])
  })

  it('revoke without entity clears all holders', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ allow_multi_role: true }), makeStubGame(),
    )! as any
    rt.assign('leader', 'erik')
    rt.assign('leader', 'baleog')
    expect(rt.revoke('leader')).toBe(true)
    expect(rt.holdersOf('leader')).toEqual([])
  })

  it('swap returns prior holder', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.assign('player_controlled', 'erik')
    expect(rt.swap('player_controlled', 'baleog')).toBe('erik')
    expect(rt.holdersOf('player_controlled')).toEqual(['baleog'])
  })

  it('swap returns null for empty role', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    expect(rt.swap('player_controlled', 'erik')).toBe(null)
  })

  it('rolesHeldBy returns all roles a single entity holds', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ allow_multi_role: true }), makeStubGame(),
    )! as any
    rt.assign('leader', 'erik')
    rt.assign('healer', 'erik')
    const roles = rt.rolesHeldBy('erik').sort()
    expect(roles).toEqual(['healer', 'leader'])
  })

  it('assignable_tag filters entities without the tag', () => {
    const scene = [
      { id: 'viking', tags: ['ally', 'playable'] },
      { id: 'enemy', tags: ['enemy'] },
    ]
    const rt = mechanicRegistry.create(
      makeInstance({ assignable_tag: 'playable' }),
      makeStubGame(scene),
    )! as any
    expect(rt.assign('player_controlled', 'viking')).toBe(true)
    expect(rt.assign('player_controlled', 'enemy')).toBe(false)
  })

  it('expose() surfaces live role_assignments dict', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ initial_assignments: { leader: 'erik' } }),
      makeStubGame(),
    )! as any
    const snap = rt.expose() as any
    expect(snap.role_assignments.leader).toEqual(['erik'])
    expect(snap.role_count).toBe(4)
    expect(snap.allow_multi_role).toBe(false)
  })

  it('dispose clears all state', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.assign('leader', 'erik')
    rt.dispose()
    expect(rt.listRoles()).toEqual([])
  })
})
