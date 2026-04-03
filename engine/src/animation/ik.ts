/**
 * Inverse Kinematics — Two-bone IK and FABRIK.
 * Used for foot placement, aiming, hand IK.
 */

import { Vec3, vec3 } from '../math/vec'
import { Quat, quat } from '../math/quat'
import { Skeleton } from './skeleton'

/**
 * Two-bone IK solver (shoulder-elbow-hand or hip-knee-foot).
 * Solves the triangle formed by bone0→bone1→effector to reach target.
 */
export function solveTwoBoneIK(
  skeleton: Skeleton,
  bone0Index: number,  // upper (shoulder/hip)
  bone1Index: number,  // middle (elbow/knee)
  effectorIndex: number, // end (hand/foot)
  target: Vec3,
  poleTarget?: Vec3,   // hint direction for elbow/knee bend
  weight = 1.0
): void {
  skeleton.computeJointMatrices()

  const p0 = skeleton.getBoneWorldPosition(bone0Index)
  const p1 = skeleton.getBoneWorldPosition(bone1Index)
  const p2 = skeleton.getBoneWorldPosition(effectorIndex)

  const lenA = vec3.distance(p0, p1) // upper bone length
  const lenB = vec3.distance(p1, p2) // lower bone length
  const lenTarget = vec3.distance(p0, target)

  // Clamp target to reachable range
  const maxReach = lenA + lenB - 0.001
  const minReach = Math.abs(lenA - lenB) + 0.001
  const clampedLen = Math.max(minReach, Math.min(maxReach, lenTarget))

  // Law of cosines: angle at bone0
  const cosAngle0 = (lenA * lenA + clampedLen * clampedLen - lenB * lenB) / (2 * lenA * clampedLen)
  const angle0 = Math.acos(Math.max(-1, Math.min(1, cosAngle0)))

  // Angle at bone1
  const cosAngle1 = (lenA * lenA + lenB * lenB - clampedLen * clampedLen) / (2 * lenA * lenB)
  const angle1 = Math.acos(Math.max(-1, Math.min(1, cosAngle1)))

  // Direction from bone0 to target
  const toTarget = vec3.normalize(vec3.create(), vec3.sub(vec3.create(), target, p0))

  // Compute pole vector for bend direction
  let poleDir: Vec3
  if (poleTarget) {
    const toMid = vec3.sub(vec3.create(), p1, p0)
    const toPole = vec3.sub(vec3.create(), poleTarget, p0)
    // Project pole onto plane perpendicular to bone chain
    const dot = vec3.dot(toPole, toTarget)
    poleDir = vec3.normalize(vec3.create(), [
      toPole[0] - toTarget[0] * dot,
      toPole[1] - toTarget[1] * dot,
      toPole[2] - toTarget[2] * dot,
    ])
  } else {
    // Default: use current bend direction
    const toMid = vec3.sub(vec3.create(), p1, p0)
    const dot = vec3.dot(toMid, toTarget)
    poleDir = vec3.normalize(vec3.create(), [
      toMid[0] - toTarget[0] * dot,
      toMid[1] - toTarget[1] * dot,
      toMid[2] - toTarget[2] * dot,
    ])
  }

  // Compute new joint positions
  const sinA0 = Math.sin(angle0)
  const cosA0 = Math.cos(angle0)
  const newP1: Vec3 = [
    p0[0] + (toTarget[0] * cosA0 + poleDir[0] * sinA0) * lenA,
    p0[1] + (toTarget[1] * cosA0 + poleDir[1] * sinA0) * lenA,
    p0[2] + (toTarget[2] * cosA0 + poleDir[2] * sinA0) * lenA,
  ]

  // Apply weight: lerp between original and solved positions
  if (weight < 1.0) {
    vec3.lerp(newP1, p1, newP1, weight)
  }

  // Write back as bone-local translations (simplified — works for chains)
  const parent0 = skeleton.parents[bone1Index]
  if (parent0 >= 0) {
    const parentPos = skeleton.getBoneWorldPosition(parent0)
    const localPos: Vec3 = [
      newP1[0] - parentPos[0],
      newP1[1] - parentPos[1],
      newP1[2] - parentPos[2],
    ]
    const o = bone1Index * 3
    skeleton.translations[o] = localPos[0]
    skeleton.translations[o + 1] = localPos[1]
    skeleton.translations[o + 2] = localPos[2]
  }
}

/**
 * FABRIK (Forward And Backward Reaching Inverse Kinematics).
 * Works on arbitrary-length chains. Good for tails, tentacles, spines.
 *
 * @param positions World-space joint positions (modified in place)
 * @param target Target position for the end effector
 * @param iterations Number of solver iterations (higher = more accurate)
 */
export function solveFABRIK(
  positions: Vec3[],
  target: Vec3,
  iterations = 10,
  tolerance = 0.001
): void {
  const n = positions.length
  if (n < 2) return

  // Compute bone lengths
  const lengths: number[] = []
  let totalLength = 0
  for (let i = 0; i < n - 1; i++) {
    const len = vec3.distance(positions[i], positions[i + 1])
    lengths.push(len)
    totalLength += len
  }

  // Check if target is reachable
  const rootToTarget = vec3.distance(positions[0], target)
  if (rootToTarget > totalLength) {
    // Stretch toward target
    const dir = vec3.normalize(vec3.create(), vec3.sub(vec3.create(), target, positions[0]))
    let dist = 0
    for (let i = 1; i < n; i++) {
      dist += lengths[i - 1]
      positions[i] = [
        positions[0][0] + dir[0] * dist,
        positions[0][1] + dir[1] * dist,
        positions[0][2] + dir[2] * dist,
      ]
    }
    return
  }

  const root: Vec3 = [...positions[0]]

  for (let iter = 0; iter < iterations; iter++) {
    // Check convergence
    const endDist = vec3.distance(positions[n - 1], target)
    if (endDist < tolerance) break

    // Forward pass: end → root
    positions[n - 1] = [...target]
    for (let i = n - 2; i >= 0; i--) {
      const dir = vec3.normalize(
        vec3.create(),
        vec3.sub(vec3.create(), positions[i], positions[i + 1])
      )
      positions[i] = [
        positions[i + 1][0] + dir[0] * lengths[i],
        positions[i + 1][1] + dir[1] * lengths[i],
        positions[i + 1][2] + dir[2] * lengths[i],
      ]
    }

    // Backward pass: root → end
    positions[0] = root
    for (let i = 1; i < n; i++) {
      const dir = vec3.normalize(
        vec3.create(),
        vec3.sub(vec3.create(), positions[i], positions[i - 1])
      )
      positions[i] = [
        positions[i - 1][0] + dir[0] * lengths[i - 1],
        positions[i - 1][1] + dir[1] * lengths[i - 1],
        positions[i - 1][2] + dir[2] * lengths[i - 1],
      ]
    }
  }
}
