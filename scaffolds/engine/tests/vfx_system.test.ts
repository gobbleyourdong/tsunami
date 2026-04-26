import { describe, it, expect } from 'vitest'
import { VFXSystem } from '../src/character3d/vfx_system'

describe('VFXSystem', () => {
  it('starts empty', () => {
    const v = new VFXSystem()
    expect(v.count()).toBe(0)
    expect(v.getPrimitives(0)).toEqual([])
  })

  it('spawnSwipe registers a swipe instance', () => {
    const v = new VFXSystem()
    v.spawnSwipe(0, 7, [0, 0.1, 0], 12, 14)
    expect(v.count()).toBe(1)
    const prims = v.getPrimitives(0)
    expect(prims.length).toBe(1)
    expect(prims[0].type).toBe(8)            // swipeArc primitive
    expect(prims[0].boneIdx).toBe(7)
    expect(prims[0].paletteSlot).toBe(12)
    expect(prims[0].unlit).toBe(true)        // VFX always unlit
  })

  it('update prunes expired instances', () => {
    const v = new VFXSystem()
    v.spawnSwipe(0, 0, [0, 0, 0], 10, 11, { duration: 0.25 })
    v.spawnTrail(0, 0, [0, 0, 0], 10,        { duration: 0.55 })
    expect(v.count()).toBe(2)
    // At t=0.30 the swipe is gone, trail still alive.
    v.update(0.30)
    expect(v.count()).toBe(1)
    expect(v.getPrimitives(0.30)[0].type).toBe(9)   // logPolarTrail
    // At t=1.0 both gone.
    v.update(1.0)
    expect(v.count()).toBe(0)
  })

  it('clear empties all instances', () => {
    const v = new VFXSystem()
    v.spawnImpactStar(0, 0, [0, 0, 0], 10)
    v.spawnMuzzleFlash(0, 0, [0, 0, 0], 12, 14)
    expect(v.count()).toBe(2)
    v.clear()
    expect(v.count()).toBe(0)
  })

  it('size opt scales primitive params', () => {
    const v = new VFXSystem()
    v.spawnSwipe(0, 0, [0, 0, 0], 10, 11, { size: 2 })
    const prim = v.getPrimitives(0)[0]
    // Swipe major radius is 0.30 * size.
    expect(prim.params[0]).toBeCloseTo(0.6)
  })

  it('swipe arc grows from 0 to π over duration', () => {
    const v = new VFXSystem()
    v.spawnSwipe(0, 0, [0, 0, 0], 10, 11, { duration: 1 })
    const prim0 = v.getPrimitives(0)[0]
    const primMid = v.getPrimitives(0.5)[0]
    const primEnd = v.getPrimitives(1.0)[0]
    expect(prim0.params[2]).toBeCloseTo(0)            // arc t=0
    expect(primMid.params[2]).toBeCloseTo(Math.PI / 2)
    expect(primEnd.params[2]).toBeCloseTo(Math.PI)
  })

  it('trail amplitude decays with age', () => {
    const v = new VFXSystem()
    v.spawnTrail(0, 0, [0, 0, 0], 10, { duration: 1 })
    const ampAt = (t: number) => v.getPrimitives(t)[0].params[0]
    expect(ampAt(0)).toBeGreaterThan(ampAt(0.5))
    expect(ampAt(0.5)).toBeGreaterThan(ampAt(0.9))
  })

  it('muzzle flash humps sin(πt) — peak at t=0.5', () => {
    const v = new VFXSystem()
    v.spawnMuzzleFlash(0, 0, [0, 0, 0], 12, 14, { duration: 1 })
    const radiusAt = (t: number) => v.getPrimitives(t)[0].params[0]
    expect(radiusAt(0)).toBeCloseTo(0)
    expect(radiusAt(0.5)).toBeGreaterThan(radiusAt(0.25))
    expect(radiusAt(1)).toBeCloseTo(0)
  })

  it('orbitGlow has long default duration (2s)', () => {
    const v = new VFXSystem()
    v.spawnOrbitGlow(0, 0, [0, 0, 0], 12, 14)
    expect(v.count()).toBe(1)
    v.update(1.5)
    expect(v.count()).toBe(1)   // still alive
    v.update(2.5)
    expect(v.count()).toBe(0)
  })
})
