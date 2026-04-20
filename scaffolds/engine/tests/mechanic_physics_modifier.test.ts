/**
 * Phase 3 residual — PhysicsModifier runtime smoke test.
 *
 * Verifies:
 * - Registers with the mechanic registry
 * - Initial params applied on init
 * - setGravityScale / setFrictionScale / setTimeScale update state
 * - setTimeScale clamps negative input to 0 (negatives go to TimeReverseMechanic)
 * - setAll atomic update of all three scales
 * - dispose restores defaults
 * - expose() surfaces current scales + affects_tag
 */

import { describe, it, expect } from 'vitest'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicInstance, PhysicsModifierParams } from '../src/design/schema'

function makeStubGame(): any {
  return { sceneManager: { activeScene: () => ({ entities: [] }) } }
}

function makeInstance(params: Partial<PhysicsModifierParams> = {}): MechanicInstance {
  return {
    id: 'phys_test',
    type: 'PhysicsModifier',
    params: {
      gravity_scale: 1.0,
      friction_scale: 1.0,
      time_scale: 1.0,
      ...params,
    } as PhysicsModifierParams,
  }
}

describe('Phase 3 — PhysicsModifier runtime', () => {
  it('is registered in the mechanic registry', () => {
    expect(mechanicRegistry.has('PhysicsModifier')).toBe(true)
  })

  it('initial params apply on init', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ gravity_scale: 0.5, friction_scale: 0.8, time_scale: 0.3 }),
      makeStubGame(),
    )! as any
    expect(rt.getGravityScale()).toBe(0.5)
    expect(rt.getFrictionScale()).toBe(0.8)
    expect(rt.getTimeScale()).toBe(0.3)
  })

  it('setGravityScale handles inversion (VVVVVV flip)', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.setGravityScale(-1.0)
    expect(rt.getGravityScale()).toBe(-1.0)
  })

  it('setFrictionScale updates state', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.setFrictionScale(2.0)
    expect(rt.getFrictionScale()).toBe(2.0)
  })

  it('setTimeScale handles slow-mo (Superhot)', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.setTimeScale(0.1)
    expect(rt.getTimeScale()).toBeCloseTo(0.1, 4)
  })

  it('setTimeScale clamps negative input to 0', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.setTimeScale(-0.5)
    expect(rt.getTimeScale()).toBe(0)
  })

  it('setAll atomic update of all three scales', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.setAll(0.25, 1.5, 0.5)
    expect(rt.getGravityScale()).toBe(0.25)
    expect(rt.getFrictionScale()).toBe(1.5)
    expect(rt.getTimeScale()).toBe(0.5)
  })

  it('affects_tag surfaces through expose', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ affects_tag: 'player' }), makeStubGame(),
    )! as any
    const snap = rt.expose() as any
    expect(snap.affects_tag).toBe('player')
  })

  it('expose() returns the live scales', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ gravity_scale: 0.8, friction_scale: 1.2, time_scale: 1.5 }),
      makeStubGame(),
    )! as any
    const snap = rt.expose() as any
    expect(snap.gravity_scale).toBe(0.8)
    expect(snap.friction_scale).toBe(1.2)
    expect(snap.time_scale).toBe(1.5)
  })

  it('dispose restores defaults', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ gravity_scale: 0.25, friction_scale: 0.5, time_scale: 0.1 }),
      makeStubGame(),
    )! as any
    rt.dispose()
    expect(rt.getGravityScale()).toBe(1.0)
    expect(rt.getFrictionScale()).toBe(1.0)
    expect(rt.getTimeScale()).toBe(1.0)
  })
})
