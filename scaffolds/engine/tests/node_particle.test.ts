import { describe, it, expect } from 'vitest'
import {
  createNodeParticle,
  tickNodeParticle,
  tickChain,
  lookAtEuler,
} from '../src/character3d/node_particle'
import type { Vec3 } from '../src/math/vec'

describe('NodeParticle creation', () => {
  it('defaults min/max length to ±5% of restLength', () => {
    const p = createNodeParticle({
      parentRef: 0,
      parentKind: 'bone',
      restOffset: [0, -0.18, 0],
      restLength: 0.18,
    })
    expect(p.minLength).toBeCloseTo(0.18 * 0.95)
    expect(p.maxLength).toBeCloseTo(0.18 * 1.05)
    expect(p.initialised).toBe(false)
    expect(p.position).toEqual([0, 0, 0])
    expect(p.prevParentPos).toEqual([0, 0, 0])
  })

  it('honours custom min/max length overrides', () => {
    const p = createNodeParticle({
      parentRef: 0,
      parentKind: 'bone',
      restOffset: [0, 0, 0],
      restLength: 1,
      minLength: 0.5,
      maxLength: 1.5,
    })
    expect(p.minLength).toBe(0.5)
    expect(p.maxLength).toBe(1.5)
  })

  it('clones restOffset to prevent caller mutation', () => {
    const off: Vec3 = [1, 2, 3]
    const p = createNodeParticle({
      parentRef: 0, parentKind: 'bone', restOffset: off, restLength: 1,
    })
    off[0] = 999
    expect(p.restOffset).toEqual([1, 2, 3])
  })
})

describe('NodeParticle.tick', () => {
  it('first tick seeds position from parent + restOffset (no origin snap)', () => {
    const p = createNodeParticle({
      parentRef: 0, parentKind: 'bone',
      restOffset: [0, -0.2, 0],
      restLength: 0.2,
    })
    const parentPos: Vec3 = [5, 10, 0]
    const getBone = (_: number): Vec3 => parentPos
    tickNodeParticle(p, [], getBone, [0, -0.2, 0])
    expect(p.position).toEqual([5, 9.8, 0])
    expect(p.prevParentPos).toEqual([5, 10, 0])
    expect(p.initialised).toBe(true)
  })

  it('second tick reads stale parent position (one-frame lag)', () => {
    const p = createNodeParticle({
      parentRef: 0, parentKind: 'bone',
      restOffset: [0, -1, 0],
      restLength: 1,
      minLength: 0.99,
      maxLength: 1.01,
    })
    let parentPos: Vec3 = [0, 0, 0]
    const getBone = (_: number): Vec3 => parentPos
    // Frame 1 — initialise at parent + offset.
    tickNodeParticle(p, [], getBone, [0, -1, 0])
    expect(p.position).toEqual([0, -1, 0])
    // Move parent +X by 0.5 next frame. Particle should end up clamped
    // to length 1 from the NEW parent pos but driven toward STALE parent
    // (which is still origin).
    parentPos = [0.5, 0, 0]
    tickNodeParticle(p, [], getBone, [0, -1, 0])
    // Stale target = (0,0,0) + (0,-1,0) = (0, -1, 0).
    // Distance from parentNow (0.5, 0, 0) to (0, -1, 0) = sqrt(.25 + 1) ≈ 1.118.
    // Clamped to maxLength = 1.01 → particle pulled toward parentNow.
    const dx = p.position[0] - 0.5
    const dy = p.position[1]
    const dz = p.position[2]
    const dist = Math.hypot(dx, dy, dz)
    expect(dist).toBeCloseTo(1.01, 3)
  })

  it('chain particle reads its prev-particle parent', () => {
    const root = createNodeParticle({
      parentRef: 0, parentKind: 'bone',
      restOffset: [0, -0.5, 0], restLength: 0.5,
    })
    const tip = createNodeParticle({
      parentRef: 0,                    // index 0 in particles[]
      parentKind: 'particle',
      restOffset: [0, -0.5, 0], restLength: 0.5,
    })
    const particles = [root, tip]
    const getBone = (_: number): Vec3 => [0, 0, 0]
    // Tick root, then tip. Root gets initialised at (0, -0.5, 0).
    tickNodeParticle(root, particles, getBone, [0, -0.5, 0])
    // Tip's parent (root) is now at (0, -0.5, 0). Tip should land at
    // (0, -1.0, 0) (parent + offset).
    tickNodeParticle(tip, particles, getBone, [0, -0.5, 0])
    expect(tip.position).toEqual([0, -1.0, 0])
    expect(tip.prevParentPos).toEqual([0, -0.5, 0])
  })

  it('tickChain ticks particles in order', () => {
    const root = createNodeParticle({
      parentRef: 0, parentKind: 'bone',
      restOffset: [0, -0.3, 0], restLength: 0.3,
    })
    const mid = createNodeParticle({
      parentRef: 0, parentKind: 'particle',
      restOffset: [0, -0.3, 0], restLength: 0.3,
    })
    const tip = createNodeParticle({
      parentRef: 1, parentKind: 'particle',
      restOffset: [0, -0.3, 0], restLength: 0.3,
    })
    const particles = [root, mid, tip]
    tickChain(particles, () => [0, 0, 0], [
      [0, -0.3, 0], [0, -0.3, 0], [0, -0.3, 0],
    ])
    expect(root.position[1]).toBeCloseTo(-0.3)
    expect(mid.position[1]).toBeCloseTo(-0.6)
    expect(tip.position[1]).toBeCloseTo(-0.9)
  })
})

describe('lookAtEuler', () => {
  it('returns 0 for from == to (degenerate, no division by zero)', () => {
    const [pitch, yaw, roll] = lookAtEuler([0, 0, 0], [0, 0, 0])
    expect(Number.isFinite(pitch)).toBe(true)
    expect(Number.isFinite(yaw)).toBe(true)
    expect(roll).toBe(0)
  })

  it('rolls yaw around Y axis for pure-XZ direction', () => {
    // Direction (1, 0, 0) → atan2(1, 0) = π/2.
    const [pitch, yaw] = lookAtEuler([0, 0, 0], [1, 0, 0])
    expect(yaw).toBeCloseTo(Math.PI / 2)
    expect(pitch).toBeCloseTo(0)
  })

  it('pitches up for negative-Y direction (-Y points toward target)', () => {
    // Direction (0, -1, 0) → asin(-(-1)/1) = π/2 = "look down by 90°".
    const [pitch] = lookAtEuler([0, 0, 0], [0, -1, 0])
    expect(pitch).toBeCloseTo(Math.PI / 2)
  })
})
