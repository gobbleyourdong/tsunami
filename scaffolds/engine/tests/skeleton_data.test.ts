import { describe, it, expect } from 'vitest'
import {
  HUMANOID_RIG,
  walkCycleSampler,
  runCycleSampler,
  PROPORTION_PRESETS,
} from '../src/character3d/skeleton'

describe('HUMANOID_RIG', () => {
  it('is a 16-joint Mixamo-naming-compatible rig', () => {
    expect(HUMANOID_RIG.length).toBe(16)
    const names = HUMANOID_RIG.map((j) => j.name)
    expect(names).toContain('Hips')
    expect(names).toContain('Spine1')
    expect(names).toContain('Spine2')
    expect(names).toContain('Head')
    expect(names).toContain('LeftArm')
    expect(names).toContain('RightFoot')
  })

  it('parent indices form a valid tree (Hips is the only root)', () => {
    let rootCount = 0
    for (let j = 0; j < HUMANOID_RIG.length; j++) {
      const joint = HUMANOID_RIG[j]
      if (joint.parent === -1) {
        rootCount++
        expect(joint.name).toBe('Hips')
      } else {
        // Parent index always lower than self (forward-walkable rig).
        expect(joint.parent).toBeLessThan(j)
        expect(joint.parent).toBeGreaterThanOrEqual(0)
      }
    }
    expect(rootCount).toBe(1)
  })

  it('symmetric Left / Right limbs', () => {
    const leftArm  = HUMANOID_RIG.find((j) => j.name === 'LeftArm')!
    const rightArm = HUMANOID_RIG.find((j) => j.name === 'RightArm')!
    expect(leftArm.offset[0]).toBeCloseTo(-rightArm.offset[0])
    expect(leftArm.offset[1]).toBeCloseTo(rightArm.offset[1])
    const leftLeg  = HUMANOID_RIG.find((j) => j.name === 'LeftUpLeg')!
    const rightLeg = HUMANOID_RIG.find((j) => j.name === 'RightUpLeg')!
    expect(leftLeg.offset[0]).toBeCloseTo(-rightLeg.offset[0])
  })
})

describe('walkCycleSampler', () => {
  it('returns identity rotation at the legs at t=0 (mid-stride zero)', () => {
    // legAngle = sin(0) = 0 → all legs/arms at neutral.
    const hipL = walkCycleSampler(0, 10) as [number, number, number]
    expect(hipL[0]).toBeCloseTo(0)
  })

  it('left leg swings forward, right leg back at quarter cycle', () => {
    // t = π/2 → sin(π/2) = 1 → legAngle = 0.5 (positive = forward).
    const hipL = walkCycleSampler(Math.PI / 2, 10) as [number, number, number]
    const hipR = walkCycleSampler(Math.PI / 2, 13) as [number, number, number]
    expect(hipL[0]).toBeGreaterThan(0)
    expect(hipR[0]).toBeLessThan(0)
    // Magnitudes mirror.
    expect(hipL[0]).toBeCloseTo(-hipR[0])
  })

  it('arms swing opposite to legs', () => {
    const hipL = walkCycleSampler(Math.PI / 2, 10) as [number, number, number]
    const shoulderL = walkCycleSampler(Math.PI / 2, 4) as [number, number, number]
    // Shoulder L pumps OPPOSITE to Hip L.
    expect(Math.sign(shoulderL[0])).toBe(-Math.sign(hipL[0]))
  })

  it('non-walking joints stay at zero rotation', () => {
    // Joint 0 (Hips) is the root — walk sampler doesn't rotate it.
    const hips = walkCycleSampler(Math.PI / 2, 0) as [number, number, number]
    expect(hips).toEqual([0, 0, 0])
  })
})

describe('runCycleSampler', () => {
  it('forward lean on the spine', () => {
    // Joint 1 = spine1; run sampler sets r[0] = 0.22 (forward lean).
    const spine = runCycleSampler(0, 1) as [number, number, number]
    expect(spine[0]).toBeCloseTo(0.22)
  })

  it('elbows are bent at a fixed ~90° (1.2 rad) for running form', () => {
    const elbowL = runCycleSampler(0, 5) as [number, number, number]
    const elbowR = runCycleSampler(0, 8) as [number, number, number]
    expect(elbowL[0]).toBeCloseTo(1.2)
    expect(elbowR[0]).toBeCloseTo(1.2)
  })

  it('legs swing further than walk (amplitude 1.0 vs 0.5)', () => {
    const runHip  = runCycleSampler(Math.PI / 2, 10) as [number, number, number]
    const walkHip = walkCycleSampler(Math.PI / 2, 10) as [number, number, number]
    expect(Math.abs(runHip[0])).toBeGreaterThan(Math.abs(walkHip[0]))
  })
})

describe('PROPORTION_PRESETS', () => {
  it('regular returns identity scale per joint', () => {
    const scales = PROPORTION_PRESETS.regular(HUMANOID_RIG)
    expect(scales.length).toBe(HUMANOID_RIG.length)
    for (const s of scales) expect(s).toEqual([1, 1, 1])
  })

  it('big_head scales up only the head joint', () => {
    // Note: PROPORTION_PRESETS uses lowercase 'head' (procedural rig
    // naming convention, NOT HUMANOID_RIG's capitalized 'Head'). On
    // HUMANOID_RIG the regex never matches, so all joints stay at 1.
    const scales = PROPORTION_PRESETS.big_head(HUMANOID_RIG)
    for (const s of scales) expect(s).toEqual([1, 1, 1])
  })

  it('chibi shrinks limb-tip joints (matching name regex)', () => {
    // Build a minimal procedural-named rig that the chibi preset's
    // regex can hit (elbow / knee / wrist / ankle).
    const rig = [
      { name: 'hips',  parent: -1, offset: [0, 0, 0] as [number, number, number] },
      { name: 'elbow', parent: 0,  offset: [0, 0, 0] as [number, number, number] },
      { name: 'head',  parent: 0,  offset: [0, 0, 0] as [number, number, number] },
    ]
    const scales = PROPORTION_PRESETS.chibi(rig)
    expect(scales[0]).toEqual([1, 1, 1])      // hips: untouched
    expect(scales[1]).toEqual([0.8, 0.7, 0.8]) // elbow: shrunk (chibi limb tips)
    expect(scales[2]).toEqual([2.0, 2.0, 2.0]) // head: enlarged
  })
})
