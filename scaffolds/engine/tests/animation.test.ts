import { describe, it, expect } from 'vitest'
import { Skeleton } from '../src/animation/skeleton'
import { AnimationClip } from '../src/animation/clip'
import { AnimationStateMachine } from '../src/animation/state_machine'
import { solveFABRIK } from '../src/animation/ik'
import { RootMotionExtractor } from '../src/animation/root_motion'
import type { Vec3 } from '../src/math/vec'

function createTestSkeleton(boneCount = 3): Skeleton {
  const names = Array.from({ length: boneCount }, (_, i) => `bone_${i}`)
  const parents = new Int32Array(boneCount)
  parents[0] = -1
  for (let i = 1; i < boneCount; i++) parents[i] = i - 1
  const ibm = new Float32Array(boneCount * 16)
  // Identity inverse bind matrices
  for (let i = 0; i < boneCount; i++) {
    ibm[i * 16 + 0] = 1; ibm[i * 16 + 5] = 1; ibm[i * 16 + 10] = 1; ibm[i * 16 + 15] = 1
  }
  return new Skeleton(names, parents, ibm)
}

function createTestClip(): AnimationClip {
  return new AnimationClip('walk', [
    {
      boneIndex: 0,
      path: 'translation',
      interpolation: 'LINEAR',
      times: new Float32Array([0, 0.5, 1.0]),
      values: new Float32Array([0, 0, 0,  1, 0, 0,  2, 0, 0]),
    },
    {
      boneIndex: 1,
      path: 'rotation',
      interpolation: 'LINEAR',
      times: new Float32Array([0, 1.0]),
      values: new Float32Array([0, 0, 0, 1,  0, 0.7071, 0, 0.7071]),
    },
  ], 1.0)
}

describe('Skeleton', () => {
  it('initializes with identity pose', () => {
    const skel = createTestSkeleton()
    expect(skel.boneCount).toBe(3)
    // Default rotation is identity
    expect(skel.rotations[3]).toBe(1) // w of bone 0
    // Default scale is 1
    expect(skel.scales[0]).toBe(1)
  })

  it('computes joint matrices', () => {
    const skel = createTestSkeleton(2)
    skel.setBonePose(0, { translation: [5, 0, 0] })
    skel.computeJointMatrices()

    const pos = skel.getBoneWorldPosition(0)
    expect(pos[0]).toBeCloseTo(5)
  })

  it('parent-child chain propagates', () => {
    const skel = createTestSkeleton(2)
    skel.setBonePose(0, { translation: [10, 0, 0] })
    skel.setBonePose(1, { translation: [0, 5, 0] })
    skel.computeJointMatrices()

    const pos1 = skel.getBoneWorldPosition(1)
    expect(pos1[0]).toBeCloseTo(10)
    expect(pos1[1]).toBeCloseTo(5)
  })

  it('finds bone by name', () => {
    const skel = createTestSkeleton()
    expect(skel.getBoneIndex('bone_1')).toBe(1)
    expect(skel.getBoneIndex('nonexistent')).toBe(-1)
  })
})

describe('AnimationClip', () => {
  it('computes duration from keyframes', () => {
    const clip = createTestClip()
    expect(clip.duration).toBe(1.0)
  })

  it('samples translation at t=0', () => {
    const clip = createTestClip()
    const skel = createTestSkeleton()
    clip.sample(0, skel)
    expect(skel.translations[0]).toBeCloseTo(0)
  })

  it('samples translation at t=0.5', () => {
    const clip = createTestClip()
    const skel = createTestSkeleton()
    clip.sample(0.5, skel)
    expect(skel.translations[0]).toBeCloseTo(1)
  })

  it('samples translation at t=1.0', () => {
    const clip = createTestClip()
    const skel = createTestSkeleton()
    clip.sample(1.0, skel)
    expect(skel.translations[0]).toBeCloseTo(2)
  })

  it('interpolates rotation via slerp', () => {
    const clip = createTestClip()
    const skel = createTestSkeleton()
    clip.sample(0.5, skel)
    // Rotation of bone 1 should be halfway between identity and 90° Y
    const ro = 1 * 4
    const len = Math.sqrt(
      skel.rotations[ro] ** 2 + skel.rotations[ro + 1] ** 2 +
      skel.rotations[ro + 2] ** 2 + skel.rotations[ro + 3] ** 2
    )
    expect(len).toBeCloseTo(1, 3)
  })

  it('blends with weight < 1', () => {
    const clip = createTestClip()
    const skel = createTestSkeleton()
    // Set initial pose
    skel.translations[0] = 10
    // Sample at weight 0.5 — should blend toward clip value
    clip.sample(0, skel, 0.5)
    // clip value at t=0 is 0, current is 10, blend = 10 + (0-10)*0.5 = 5
    expect(skel.translations[0]).toBeCloseTo(5)
  })
})

describe('AnimationStateMachine', () => {
  it('starts in first added state', () => {
    const sm = new AnimationStateMachine()
    const clip = createTestClip()
    sm.addState('idle', clip)
    expect(sm.current).toBe('idle')
  })

  it('transitions between states', () => {
    const sm = new AnimationStateMachine()
    const idle = createTestClip()
    const walk = new AnimationClip('walk', [], 1.0)
    sm.addState('idle', idle)
    sm.addState('walk', walk)

    const skel = createTestSkeleton()
    sm.transitionTo('walk', 0.1)
    // Update enough to complete transition
    sm.update(0.2, skel)
    expect(sm.current).toBe('walk')
  })

  it('fires animation events', () => {
    const sm = new AnimationStateMachine()
    const clip = createTestClip()
    const events: string[] = []

    sm.addState('walk', clip, {
      events: [{ name: 'footstep', time: 0.5 }],
    })
    sm.onEvent = (_, name) => events.push(name)

    const skel = createTestSkeleton()
    sm.update(0.6, skel) // should fire at t=0.5
    expect(events).toContain('footstep')
  })

  it('auto-transitions on condition', () => {
    const sm = new AnimationStateMachine()
    const idle = createTestClip()
    const walk = createTestClip()
    let shouldWalk = false

    sm.addState('idle', idle)
    sm.addState('walk', walk)
    sm.addTransition('idle', 'walk', 0.1, () => shouldWalk)

    const skel = createTestSkeleton()
    sm.update(0.01, skel)
    expect(sm.current).toBe('idle')

    shouldWalk = true
    sm.update(0.01, skel)
    // Should now be transitioning
    sm.update(0.2, skel)
    expect(sm.current).toBe('walk')
  })
})

describe('FABRIK', () => {
  it('reaches target when reachable', () => {
    const positions: Vec3[] = [
      [0, 0, 0],
      [0, 1, 0],
      [0, 2, 0],
    ]
    const target: Vec3 = [1, 1, 0]
    solveFABRIK(positions, target, 20)

    const endDist = Math.sqrt(
      (positions[2][0] - target[0]) ** 2 +
      (positions[2][1] - target[1]) ** 2 +
      (positions[2][2] - target[2]) ** 2
    )
    expect(endDist).toBeLessThan(0.01)
  })

  it('preserves root position', () => {
    const positions: Vec3[] = [
      [0, 0, 0],
      [0, 1, 0],
      [0, 2, 0],
    ]
    solveFABRIK(positions, [1, 1, 0], 10)
    expect(positions[0]).toEqual([0, 0, 0])
  })

  it('stretches toward unreachable target', () => {
    const positions: Vec3[] = [
      [0, 0, 0],
      [0, 1, 0],
      [0, 2, 0],
    ]
    const target: Vec3 = [0, 100, 0] // way too far
    solveFABRIK(positions, target, 10)

    // Should stretch upward
    expect(positions[2][1]).toBeGreaterThan(positions[1][1])
    expect(positions[1][1]).toBeGreaterThan(positions[0][1])
  })

  it('preserves bone lengths', () => {
    const positions: Vec3[] = [
      [0, 0, 0],
      [0, 1, 0],
      [0, 2, 0],
    ]
    solveFABRIK(positions, [1, 1, 0], 20)

    const len0 = Math.sqrt(
      (positions[1][0] - positions[0][0]) ** 2 +
      (positions[1][1] - positions[0][1]) ** 2 +
      (positions[1][2] - positions[0][2]) ** 2
    )
    const len1 = Math.sqrt(
      (positions[2][0] - positions[1][0]) ** 2 +
      (positions[2][1] - positions[1][1]) ** 2 +
      (positions[2][2] - positions[1][2]) ** 2
    )
    expect(len0).toBeCloseTo(1, 2)
    expect(len1).toBeCloseTo(1, 2)
  })
})

describe('RootMotionExtractor', () => {
  it('extracts delta translation', () => {
    const skel = createTestSkeleton()
    const rme = new RootMotionExtractor(0)

    // First frame: set initial position
    skel.setBonePose(0, { translation: [0, 0, 0] })
    rme.reset(skel)

    // Second frame: moved
    skel.setBonePose(0, { translation: [1, 0, 2] })
    rme.extract(skel)

    expect(rme.deltaTranslation[0]).toBeCloseTo(1)
    expect(rme.deltaTranslation[2]).toBeCloseTo(2)

    // Root XZ should be zeroed out
    expect(skel.translations[0]).toBeCloseTo(0)
    expect(skel.translations[2]).toBeCloseTo(0)
  })
})
