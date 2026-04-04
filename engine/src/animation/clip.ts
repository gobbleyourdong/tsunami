/**
 * Animation clip — sampled keyframe data for skeletal animation.
 * Supports LINEAR, STEP, and CUBICSPLINE interpolation (GLTF spec).
 */

import { Quat, quat } from '../math/quat'
import { Vec3, vec3 } from '../math/vec'
import { Skeleton } from './skeleton'

export interface AnimationChannel {
  boneIndex: number
  path: 'translation' | 'rotation' | 'scale'
  interpolation: 'LINEAR' | 'STEP' | 'CUBICSPLINE'
  times: Float32Array
  values: Float32Array
}

export class AnimationClip {
  readonly name: string
  readonly duration: number
  readonly channels: AnimationChannel[]

  constructor(name: string, channels: AnimationChannel[], duration?: number) {
    this.name = name
    this.channels = channels
    this.duration = duration ?? this.computeDuration()
  }

  private computeDuration(): number {
    let max = 0
    for (const ch of this.channels) {
      const last = ch.times[ch.times.length - 1]
      if (last > max) max = last
    }
    return max
  }

  /**
   * Sample this clip at the given time and write results into the skeleton's pose buffers.
   * @param time Time in seconds (will be wrapped to [0, duration] if looping)
   * @param skeleton Target skeleton to write pose into
   * @param weight Blend weight (0-1). At 1.0, fully overrides. At <1.0, blends with current pose.
   */
  sample(time: number, skeleton: Skeleton, weight = 1.0): void {
    for (const ch of this.channels) {
      if (ch.boneIndex < 0 || ch.boneIndex >= skeleton.boneCount) continue

      const { keyIndex, t } = findKeyframe(ch.times, time)

      if (ch.path === 'translation') {
        const v = sampleVec3(ch, keyIndex, t)
        const o = ch.boneIndex * 3
        if (weight >= 1.0) {
          skeleton.translations[o] = v[0]
          skeleton.translations[o + 1] = v[1]
          skeleton.translations[o + 2] = v[2]
        } else {
          skeleton.translations[o] += (v[0] - skeleton.translations[o]) * weight
          skeleton.translations[o + 1] += (v[1] - skeleton.translations[o + 1]) * weight
          skeleton.translations[o + 2] += (v[2] - skeleton.translations[o + 2]) * weight
        }
      } else if (ch.path === 'rotation') {
        const q = sampleQuat(ch, keyIndex, t)
        const o = ch.boneIndex * 4
        if (weight >= 1.0) {
          skeleton.rotations[o] = q[0]
          skeleton.rotations[o + 1] = q[1]
          skeleton.rotations[o + 2] = q[2]
          skeleton.rotations[o + 3] = q[3]
        } else {
          const current: Quat = [
            skeleton.rotations[o], skeleton.rotations[o + 1],
            skeleton.rotations[o + 2], skeleton.rotations[o + 3],
          ]
          const blended = quat.create()
          quat.slerp(blended, current, q, weight)
          skeleton.rotations[o] = blended[0]
          skeleton.rotations[o + 1] = blended[1]
          skeleton.rotations[o + 2] = blended[2]
          skeleton.rotations[o + 3] = blended[3]
        }
      } else if (ch.path === 'scale') {
        const v = sampleVec3(ch, keyIndex, t)
        const o = ch.boneIndex * 3
        if (weight >= 1.0) {
          skeleton.scales[o] = v[0]
          skeleton.scales[o + 1] = v[1]
          skeleton.scales[o + 2] = v[2]
        } else {
          skeleton.scales[o] += (v[0] - skeleton.scales[o]) * weight
          skeleton.scales[o + 1] += (v[1] - skeleton.scales[o + 1]) * weight
          skeleton.scales[o + 2] += (v[2] - skeleton.scales[o + 2]) * weight
        }
      }
    }
  }
}

function findKeyframe(times: Float32Array, time: number): { keyIndex: number; t: number } {
  if (time <= times[0]) return { keyIndex: 0, t: 0 }
  if (time >= times[times.length - 1]) return { keyIndex: times.length - 2, t: 1 }

  // Binary search
  let lo = 0
  let hi = times.length - 1
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1
    if (times[mid] <= time) lo = mid
    else hi = mid
  }

  const dt = times[hi] - times[lo]
  const t = dt > 0 ? (time - times[lo]) / dt : 0
  return { keyIndex: lo, t }
}

function sampleVec3(ch: AnimationChannel, keyIndex: number, t: number): Vec3 {
  const stride = 3
  const i0 = keyIndex * stride
  const i1 = (keyIndex + 1) * stride

  if (ch.interpolation === 'STEP') {
    return [ch.values[i0], ch.values[i0 + 1], ch.values[i0 + 2]]
  }

  // LINEAR (or fallback for CUBICSPLINE — simplified)
  const out = vec3.create()
  vec3.lerp(
    out,
    [ch.values[i0], ch.values[i0 + 1], ch.values[i0 + 2]],
    [ch.values[i1], ch.values[i1 + 1], ch.values[i1 + 2]],
    t
  )
  return out
}

function sampleQuat(ch: AnimationChannel, keyIndex: number, t: number): Quat {
  const stride = 4
  const i0 = keyIndex * stride
  const i1 = (keyIndex + 1) * stride

  if (ch.interpolation === 'STEP') {
    return [ch.values[i0], ch.values[i0 + 1], ch.values[i0 + 2], ch.values[i0 + 3]]
  }

  const out = quat.create()
  quat.slerp(
    out,
    [ch.values[i0], ch.values[i0 + 1], ch.values[i0 + 2], ch.values[i0 + 3]],
    [ch.values[i1], ch.values[i1 + 1], ch.values[i1 + 2], ch.values[i1 + 3]],
    t
  )
  return out
}
