import { describe, it, expect } from 'vitest'
import {
  extendRigWithBodyParts,
  extendLocalMatsWithBodyParts,
  extendRigWithHair,
  extendRigWithAccessories,
  type BodyPart,
  type HairPart,
  type Accessory,
} from '../src/character3d/mixamo_loader'
import type { Joint } from '../src/character3d/skeleton'

const BASE_RIG: Joint[] = [
  { name: 'Hips',    parent: -1, offset: [0, 1, 0] },
  { name: 'Spine',   parent: 0,  offset: [0, 0.1, 0] },
  { name: 'Spine2',  parent: 1,  offset: [0, 0.2, 0] },
  { name: 'Head',    parent: 2,  offset: [0, 0.15, 0] },
  { name: 'LeftFoot', parent: 0, offset: [0.1, -1, 0] },
]

describe('extendRigWithBodyParts', () => {
  it('appends parts as joints, parent index resolves by name', () => {
    const items: BodyPart[] = [
      { name: 'WP_ChestPlate', parentName: 'Spine2', offset: [0, 0, 0.04], displaySize: [0.2, 0.18, 0.14] },
      { name: 'WP_BootL',      parentName: 'LeftFoot', offset: [0, 0.04, 0], displaySize: [0.06, 0.08, 0.11] },
    ]
    const out = extendRigWithBodyParts(BASE_RIG, items)
    expect(out.length).toBe(BASE_RIG.length + 2)
    const chest = out[BASE_RIG.length]
    expect(chest.name).toBe('WP_ChestPlate')
    expect(chest.parent).toBe(2)        // Spine2
    expect(chest.offset).toEqual([0, 0, 0.04])
    const boot = out[BASE_RIG.length + 1]
    expect(boot.parent).toBe(4)         // LeftFoot
  })

  it('does not mutate the input rig', () => {
    const before = BASE_RIG.length
    extendRigWithBodyParts(BASE_RIG, [
      { name: 'X', parentName: 'Hips', offset: [0, 0, 0], displaySize: [0.05, 0.05, 0.05] },
    ])
    expect(BASE_RIG.length).toBe(before)
  })

  it('skips parts whose parent is missing (warns, no throw)', () => {
    const items: BodyPart[] = [
      { name: 'OrphanPart', parentName: 'NotABone', offset: [0, 0, 0], displaySize: [0.1, 0.1, 0.1] },
    ]
    const out = extendRigWithBodyParts(BASE_RIG, items)
    expect(out.length).toBe(BASE_RIG.length)   // not appended
  })

  it('chained parts resolve later-appended siblings as parents', () => {
    // CapeRoot parents to Spine2; CapeMid parents to CapeRoot; CapeTip
    // parents to CapeMid. Each must resolve in order.
    const items: BodyPart[] = [
      { name: 'CapeRoot', parentName: 'Spine2',  offset: [0, 0, -0.1], displaySize: [0.1, 0.05, 0.02] },
      { name: 'CapeMid',  parentName: 'CapeRoot', offset: [0, -0.18, 0], displaySize: [0.1, 0.05, 0.02] },
      { name: 'CapeTip',  parentName: 'CapeMid',  offset: [0, -0.18, 0], displaySize: [0.1, 0.05, 0.02] },
    ]
    const out = extendRigWithBodyParts(BASE_RIG, items)
    const root = out.find((j) => j.name === 'CapeRoot')!
    const mid  = out.find((j) => j.name === 'CapeMid')!
    const tip  = out.find((j) => j.name === 'CapeTip')!
    expect(out[root.parent].name).toBe('Spine2')
    expect(out[mid.parent].name).toBe('CapeRoot')
    expect(out[tip.parent].name).toBe('CapeMid')
  })
})

describe('extendLocalMatsWithBodyParts', () => {
  it('grows the local-matrix array by items.length × 16 floats per frame', () => {
    const numFrames = 3
    const origJoints = BASE_RIG.length
    const localMats = new Float32Array(numFrames * origJoints * 16)
    // Fill with sentinel values so we can confirm originals are preserved.
    for (let i = 0; i < localMats.length; i++) localMats[i] = 0.5
    const items: BodyPart[] = [
      { name: 'A', parentName: 'Hips', offset: [0.1, 0.2, 0.3], displaySize: [0.05, 0.05, 0.05] },
      { name: 'B', parentName: 'Hips', offset: [0.4, 0.5, 0.6], displaySize: [0.05, 0.05, 0.05] },
    ]
    const out = extendLocalMatsWithBodyParts(localMats, numFrames, origJoints, items)
    const newJoints = origJoints + items.length
    expect(out.length).toBe(numFrames * newJoints * 16)
    // Frame 0, slot 0 still holds sentinel 0.5.
    expect(out[0]).toBe(0.5)
    // Item A's translation column: offset (0.1, 0.2, 0.3) goes to col3 (slots 12..14).
    const aBase = origJoints * 16   // first item slot
    expect(out[aBase + 12]).toBeCloseTo(0.1)
    expect(out[aBase + 13]).toBeCloseTo(0.2)
    expect(out[aBase + 14]).toBeCloseTo(0.3)
    // Identity rotation in the upper-left 3×3 (no rotationDeg specified).
    expect(out[aBase + 0]).toBe(1)
    expect(out[aBase + 5]).toBe(1)
    expect(out[aBase + 10]).toBe(1)
  })
})

describe('extendLocalMatsWithBodyParts — rotation', () => {
  it('rotationDeg [0, 0, 90] produces a Z-axis 90° rotation matrix', () => {
    const numFrames = 1
    const origJoints = BASE_RIG.length
    const localMats = new Float32Array(numFrames * origJoints * 16)
    const items: BodyPart[] = [
      { name: 'Sash', parentName: 'Hips', offset: [0, 0, 0], rotationDeg: [0, 0, 90], displaySize: [0.05, 0.05, 0.05] },
    ]
    const out = extendLocalMatsWithBodyParts(localMats, numFrames, origJoints, items)
    const aBase = origJoints * 16
    // Rz(90°): m00 = cos(90) = 0, m01 = -sin(90) = -1, m10 = sin(90) = 1, m11 = cos(90) = 0
    // Column-major: out[0] = m00, out[1] = m10, out[4] = m01, out[5] = m11
    expect(out[aBase + 0]).toBeCloseTo(0,  5)
    expect(out[aBase + 1]).toBeCloseTo(1,  5)
    expect(out[aBase + 4]).toBeCloseTo(-1, 5)
    expect(out[aBase + 5]).toBeCloseTo(0,  5)
    // Z stays unchanged.
    expect(out[aBase + 10]).toBeCloseTo(1, 5)
  })

  it('rotationDeg [180, 0, 0] flips Y and Z signs (X-axis 180°)', () => {
    const localMats = new Float32Array(BASE_RIG.length * 16)
    const items: BodyPart[] = [
      { name: 'Flip', parentName: 'Hips', offset: [0, 0, 0], rotationDeg: [180, 0, 0], displaySize: [0.05, 0.05, 0.05] },
    ]
    const out = extendLocalMatsWithBodyParts(localMats, 1, BASE_RIG.length, items)
    const base = BASE_RIG.length * 16
    // Rx(180°): keeps X, flips Y+Z.
    expect(out[base + 0]).toBeCloseTo(1, 5)        // m00
    expect(out[base + 5]).toBeCloseTo(-1, 5)       // m11
    expect(out[base + 10]).toBeCloseTo(-1, 5)      // m22
  })

  it('every part gets a unique local matrix block', () => {
    const localMats = new Float32Array(BASE_RIG.length * 16)
    const items: BodyPart[] = [
      { name: 'A', parentName: 'Hips', offset: [1, 0, 0], displaySize: [0.05, 0.05, 0.05] },
      { name: 'B', parentName: 'Hips', offset: [0, 2, 0], displaySize: [0.05, 0.05, 0.05] },
      { name: 'C', parentName: 'Hips', offset: [0, 0, 3], displaySize: [0.05, 0.05, 0.05] },
    ]
    const out = extendLocalMatsWithBodyParts(localMats, 1, BASE_RIG.length, items)
    const base = BASE_RIG.length * 16
    expect(out[base + 0 * 16 + 12]).toBeCloseTo(1)   // A.translation.x
    expect(out[base + 1 * 16 + 13]).toBeCloseTo(2)   // B.translation.y
    expect(out[base + 2 * 16 + 14]).toBeCloseTo(3)   // C.translation.z
  })
})

describe('extendRigWithHair / extendRigWithAccessories', () => {
  it('extendRigWithHair behaves like body-parts extension', () => {
    const items: HairPart[] = [
      { name: 'HairBob', parentName: 'Head', offset: [0, 0.16, 0], displaySize: [0.22, 0.16, 0.22] },
    ]
    const out = extendRigWithHair(BASE_RIG, items)
    expect(out.length).toBe(BASE_RIG.length + 1)
    expect(out.at(-1)?.name).toBe('HairBob')
    expect(out.at(-1)?.parent).toBe(3)   // Head
  })

  it('extendRigWithAccessories appends accessory bones', () => {
    const items: Accessory[] = [
      { name: 'RightWeapon', parentName: 'Head', offset: [0, 0, 0.2], rotationDeg: [0, 0, 15], displaySize: [0.015, 0.22, 0.015] },
    ]
    const out = extendRigWithAccessories(BASE_RIG, items)
    expect(out.length).toBe(BASE_RIG.length + 1)
    expect(out.at(-1)?.name).toBe('RightWeapon')
  })
})
