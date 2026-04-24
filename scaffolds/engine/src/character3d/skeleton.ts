/**
 * Skeleton rig + per-frame world-matrix bake → VAT storage buffer.
 *
 * The bake function is SOURCE-AGNOSTIC: it takes a rig (joint hierarchy +
 * offsets) + a per-frame local-rotation function + per-joint scale array
 * and produces the same VAT buffer format whether rotations come from a
 * procedural walk cycle or a Mixamo FBX.
 *
 * Buffer layout (matches VATData.buffer semantics):
 *   index = (frameIdx * numJoints + jointIdx) * 4 = 4 consecutive vec4f
 *   = one mat4x4f (world-space joint transform at that frame)
 *
 * Shader side: reconstruct mat4 from those 4 vec4f, transform cube vertex.
 */

import { mat4, type Vec3 } from '../math/vec'
import type { VATData } from './vat'

export interface Joint {
  name: string
  parent: number                      // index into rig array; -1 for root
  offset: Vec3                        // rest-pose local translation from parent
  preRotation?: Vec3                  // FBX PreRotation (euler radians) — applied BEFORE animated rotation in the local frame
}

/** Procedural humanoid rig — 16 joints, Mixamo-compatible naming so the
 *  chibi body-part map (Head/Spine1/Hips/LeftArm/…) works on both this rig
 *  and loaded Mixamo rigs without a separate mapping. */
export const HUMANOID_RIG: Joint[] = [
  { name: 'Hips',           parent: -1, offset: [0, 0, 0] },
  { name: 'Spine1',         parent:  0, offset: [0, 0.3, 0] },
  { name: 'Spine2',         parent:  1, offset: [0, 0.3, 0] },
  { name: 'Head',           parent:  2, offset: [0, 0.3, 0] },
  { name: 'LeftArm',        parent:  2, offset: [-0.2, 0.2, 0] },
  { name: 'LeftForeArm',    parent:  4, offset: [0, -0.3, 0] },
  { name: 'LeftHand',       parent:  5, offset: [0, -0.3, 0] },
  { name: 'RightArm',       parent:  2, offset: [ 0.2, 0.2, 0] },
  { name: 'RightForeArm',   parent:  7, offset: [0, -0.3, 0] },
  { name: 'RightHand',      parent:  8, offset: [0, -0.3, 0] },
  { name: 'LeftUpLeg',      parent:  0, offset: [-0.15, 0, 0] },
  { name: 'LeftLeg',        parent: 10, offset: [0, -0.4, 0] },
  { name: 'LeftFoot',       parent: 11, offset: [0, -0.4, 0] },
  { name: 'RightUpLeg',     parent:  0, offset: [ 0.15, 0, 0] },
  { name: 'RightLeg',       parent: 13, offset: [0, -0.4, 0] },
  { name: 'RightFoot',      parent: 14, offset: [0, -0.4, 0] },
]

/** A pose-sample for one (joint, time): euler rotations (always) and
 *  optionally a translation override (used for root motion / any bone
 *  whose local translation is animated). Falling back to rig offset is
 *  the right behavior for procedural cycles; Mixamo overrides it. */
export type PoseSample = Vec3 | { r: Vec3; t?: Vec3 }

/** Per-frame pose sampler: given time t in seconds (or procedural phase)
 *  and joint index, returns a PoseSample. Procedural rigs implement this
 *  directly; Mixamo loader wraps its keyframe tables. */
export type RotationSampler = (t: number, jointIdx: number) => PoseSample

/** Higher-amplitude, forward-leaning run cycle — legs swing ~2× harder,
 *  elbows bent ~90° and pumping, torso leans forward, spine twist stronger.
 *  Same VAT format as walk; real Mixamo Running.fbx will write into this
 *  same shape via the eventual FBX loader. */
export const runCycleSampler: RotationSampler = (t, jointIdx) => {
  const r: Vec3 = [0, 0, 0]
  const legAngle = Math.sin(t) * 1.0
  const armAngle = -legAngle * 1.3
  const kneeL = Math.max(0, Math.sin(t)) * 1.3
  const kneeR = Math.max(0, -Math.sin(t)) * 1.3

  switch (jointIdx) {
    case 1:                           // spine: forward lean + twist
      r[0] = 0.22
      r[1] = Math.sin(t) * 0.18
      break
    case 4:                           // shoulder_L — pumps, elbow-bent
      r[0] = armAngle - 0.5
      break
    case 7:                           // shoulder_R
      r[0] = -armAngle - 0.5
      break
    case 5: case 8:                   // elbows bent ~90° (running form)
      r[0] = 1.2
      break
    case 10: r[0] = legAngle; break   // hip_L
    case 13: r[0] = -legAngle; break  // hip_R
    case 11: r[0] = -kneeL * 1.4; break
    case 14: r[0] = -kneeR * 1.4; break
  }
  return r
}

/** Classic hand-coded walk cycle — left leg forward while right leg back,
 *  arms swing opposite, slight spine twist + knee flexion on forward strike. */
export const walkCycleSampler: RotationSampler = (t, jointIdx) => {
  const r: Vec3 = [0, 0, 0]
  const legAngle = Math.sin(t) * 0.5
  const armAngle = -legAngle * 0.7
  const kneeL = Math.max(0, Math.sin(t)) * 0.6        // knee bends when leg forward
  const kneeR = Math.max(0, -Math.sin(t)) * 0.6

  switch (jointIdx) {
    case 1:                           // spine twist
      r[1] = Math.sin(t) * 0.1
      break
    case 4:                           // shoulder_L swings back when left leg forward
      r[0] = armAngle
      break
    case 7:                           // shoulder_R (opposite)
      r[0] = -armAngle
      break
    case 5: case 8:                   // elbows bend a touch
      r[0] = 0.3
      break
    case 10:                          // hip_L
      r[0] = legAngle
      break
    case 13:                          // hip_R
      r[0] = -legAngle
      break
    case 11:                          // knee_L
      r[0] = -kneeL
      break
    case 14:                          // knee_R
      r[0] = -kneeR
      break
  }
  return r
}

/** Bake N frames of world-space joint matrices into a GPU storage buffer
 *  or fill an existing one. Scales apply per-joint in local space →
 *  children inherit through parent chain (big head just grows the head;
 *  long limbs stretch from shoulders/hips). */
export function bakeSkeletonVAT(
  device: GPUDevice,
  rig: Joint[],
  numFrames: number,
  scales: Vec3[],
  sampler: RotationSampler,
  existing?: GPUBuffer
): VATData {
  const numJoints = rig.length
  const data = new Float32Array(numFrames * numJoints * 16)

  const worldMats: Float32Array[] = rig.map(() => mat4.create())
  const localMat = mat4.create()
  const rootPos: Vec3 = [0, 0, 0]

  for (let f = 0; f < numFrames; f++) {
    const t = (f / numFrames) * Math.PI * 2

    for (let j = 0; j < numJoints; j++) {
      mat4.identity(localMat)
      const joint = rig[j]
      const scale = scales[j] ?? [1, 1, 1]

      const sample = sampler(t, j)
      const rotation = Array.isArray(sample) ? sample : sample.r
      const sampleT  = Array.isArray(sample) ? undefined : sample.t

      // Translation: per-frame override wins; else rest offset. Root adds a
      // slight bob for procedural samplers (they have no translation track).
      if (sampleT) {
        mat4.translate(localMat, localMat, sampleT)
      } else if (joint.parent < 0) {
        rootPos[0] = joint.offset[0]
        rootPos[1] = joint.offset[1] + Math.abs(Math.sin(t * 2)) * 0.04
        rootPos[2] = joint.offset[2]
        mat4.translate(localMat, localMat, rootPos)
      } else {
        mat4.translate(localMat, localMat, joint.offset)
      }

      // NOTE: FBX PreRotation is INTENTIONALLY NOT applied here. Mixamo's
      // Lcl Rotation keyframes are stored as FULL local rotations (already
      // containing the rest-orientation info). Applying PreRotation on top
      // double-rotates and mangles the rig (tested 2026-04-23 — screenshot
      // showed character exploded into a twisted star). The `preRotation`
      // field is retained on Joint for other FBX tooling but unused here.
      const [rx, ry, rz] = rotation
      // Mixamo FBX RotationOrder=0 / eEulerXYZ. Tested 2026-04-23:
      // Rx·Ry·Rz (intrinsic XYZ) explodes at rotations > 60°.
      // Rz·Ry·Rx (extrinsic XYZ, which is what FBX SDK does for the naming
      // "eEulerXYZ" in practice — applies Z then Y then X to the vector)
      // holds together for running cycles. Choosing this order.
      if (rz !== 0) mat4.rotateZ(localMat, localMat, rz)
      if (ry !== 0) mat4.rotateY(localMat, localMat, ry)
      if (rx !== 0) mat4.rotateX(localMat, localMat, rx)
      mat4.scale(localMat, localMat, scale)

      if (joint.parent < 0) {
        worldMats[j].set(localMat)
      } else {
        mat4.multiply(worldMats[j], worldMats[joint.parent], localMat)
      }
    }

    for (let j = 0; j < numJoints; j++) {
      data.set(worldMats[j], (f * numJoints + j) * 16)
    }
  }

  let buffer: GPUBuffer
  if (existing) {
    buffer = existing
    device.queue.writeBuffer(buffer, 0, data)
  } else {
    buffer = device.createBuffer({
      label: 'skeleton-vat',
      size: data.byteLength,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    })
    device.queue.writeBuffer(buffer, 0, data)
  }

  return { buffer, numInstances: numJoints, numFrames }
}

/** Per-joint scale presets for the proportion-button system. */
export const PROPORTION_PRESETS: Record<string, (rig: Joint[]) => Vec3[]> = {
  regular: (rig) => rig.map(() => [1, 1, 1]),
  big_head: (rig) => rig.map((j) => (j.name === 'head' ? [1.8, 1.8, 1.8] : [1, 1, 1])),
  chibi: (rig) =>
    rig.map((j) => {
      if (j.name === 'head') return [2.0, 2.0, 2.0]
      if (/elbow|wrist|knee|ankle/.test(j.name)) return [0.8, 0.7, 0.8]
      return [1, 1, 1]
    }),
}
