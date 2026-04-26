import { describe, it, expect } from 'vitest'
import {
  createSecondarySpring,
  createSecondaryReader,
  tickSpring,
  tickReader,
  readerBoneEuler,
  makeDefaultCapeReader,
  makeDefaultHairReader,
} from '../src/character3d/secondary'

describe('SecondarySpring', () => {
  it('starts uninitialised at the requested rest position', () => {
    const s = createSecondarySpring([1, 2, 3])
    expect(s.position).toEqual([1, 2, 3])
    expect(s.velocity).toEqual([0, 0, 0])
    expect(s.initialised).toBe(false)
  })

  it('first tickSpring snaps to the rest target (no integration from origin)', () => {
    const s = createSecondarySpring([0, 0, 0])
    tickSpring(s, [5, 6, 7], 1 / 60)
    expect(s.position).toEqual([5, 6, 7])
    expect(s.velocity).toEqual([0, 0, 0])
    expect(s.initialised).toBe(true)
  })

  it('subsequent ticks integrate toward rest with damping', () => {
    const s = createSecondarySpring([0, 0, 0])
    // Initialise at origin.
    tickSpring(s, [0, 0, 0], 1 / 60)
    // Suddenly the rest target moves to (1, 0, 0). Spring should
    // accelerate toward it but not snap there.
    for (let i = 0; i < 20; i++) tickSpring(s, [1, 0, 0], 1 / 60)
    // After a fraction of a second the spring should have moved
    // most of the way toward (1, 0, 0) but probably not exactly there.
    expect(s.position[0]).toBeGreaterThan(0.5)
    expect(Math.abs(s.position[1])).toBeLessThan(1e-6)
    expect(Math.abs(s.position[2])).toBeLessThan(1e-6)
    // Eventually settles. Loop until velocity is small.
    for (let i = 0; i < 200; i++) tickSpring(s, [1, 0, 0], 1 / 60)
    expect(Math.abs(s.position[0] - 1)).toBeLessThan(0.01)
    expect(Math.hypot(...s.velocity)).toBeLessThan(0.01)
  })

  it('respects custom stiffness / damping', () => {
    const stiff = createSecondarySpring([0, 0, 0], { stiffness: 50, damping: 0.85 })
    expect(stiff.stiffness).toBe(50)
    expect(stiff.damping).toBe(0.85)
  })

  it('clamps oversized dt to 1/30 to keep integration stable', () => {
    // If clamping didn't happen, a 1-second dt with big spring force
    // would produce a runaway velocity. We just check the spring
    // doesn't NaN out — exact values would depend on clamp choice.
    const s = createSecondarySpring([0, 0, 0])
    tickSpring(s, [0, 0, 0], 1 / 60)
    tickSpring(s, [10, 10, 10], 1.0)   // bogus dt
    expect(Number.isFinite(s.position[0])).toBe(true)
    expect(Number.isFinite(s.velocity[0])).toBe(true)
  })
})

describe('SecondaryReader', () => {
  it('rejects mismatched scale / bones lengths', () => {
    expect(() =>
      createSecondaryReader({ bones: [0, 1], scale: [1, 2, 3] }),
    ).toThrow(/scale\.length/)
  })

  it('defaults axisMask to [1,1,1] and clones inputs', () => {
    const bones = [0, 1, 2]
    const scale = [0.1, 0.5, 1.0]
    const r = createSecondaryReader({ bones, scale })
    expect(r.axisMask).toEqual([1, 1, 1])
    expect(r.bones).toEqual(bones)
    expect(r.bones).not.toBe(bones)   // cloned
    expect(r.scale).not.toBe(scale)
  })

  it('zero responsiveness skips the low-pass and uses raw lag', () => {
    const r = createSecondaryReader({ bones: [0], scale: [1], responsiveness: 0 })
    const s = createSecondarySpring([0, 0, 0])
    tickSpring(s, [0, 0, 0], 1 / 60)
    // Spring at (0,0,0), restTarget at (1,0,0) → lag = (1, 0, 0).
    tickReader(r, s, [1, 0, 0], 1 / 60)
    expect(r.filteredLag).toEqual([1, 0, 0])
  })

  it('readerBoneEuler applies axisMask, scale, and clamp', () => {
    const r = createSecondaryReader({
      bones: [0],
      scale: [0.5],
      axisMask: [1, 0, 1],   // pitch + roll, no yaw
      maxAngleRad: 0.3,
      responsiveness: 0,
    })
    r.filteredLag[0] = 10        // huge lag — clamp should kick in
    r.filteredLag[1] = 10        // masked off
    r.filteredLag[2] = 0.4
    const [pitch, yaw, roll] = readerBoneEuler(r, 0)
    expect(pitch).toBe(0.3)       // clamped to maxAngleRad
    expect(yaw).toBe(0)           // axisMask=0 zeroes it
    expect(roll).toBeCloseTo(0.2) // 0.4 * 0.5 = 0.2 < clamp
  })

  it('default cape reader: 3-bone chain, [1,0,1] mask, tip scale > root scale', () => {
    const cape = makeDefaultCapeReader([10, 11, 12])
    expect(cape.bones).toEqual([10, 11, 12])
    expect(cape.scale.length).toBe(3)
    expect(cape.scale[0]).toBeLessThan(cape.scale[2])
    expect(cape.axisMask).toEqual([1, 0, 1])
  })

  it('default hair reader: ramps scale from 0.2 → 1.2 across N segments', () => {
    const hair = makeDefaultHairReader([20, 21, 22, 23, 24])
    expect(hair.bones.length).toBe(5)
    expect(hair.scale[0]).toBeCloseTo(0.2)
    expect(hair.scale[hair.scale.length - 1]).toBeCloseTo(1.2)
  })
})
