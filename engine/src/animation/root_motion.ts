/**
 * Root motion — extract translation/rotation from root bone animation
 * and apply to the scene node (character controller) instead.
 */

import { Vec3, vec3 } from '../math/vec'
import { Quat, quat } from '../math/quat'
import { Skeleton } from './skeleton'

export class RootMotionExtractor {
  private prevTranslation: Vec3 = [0, 0, 0]
  private prevRotation: Quat = [0, 0, 0, 1]
  private rootBoneIndex: number

  // Accumulated delta this frame
  deltaTranslation: Vec3 = [0, 0, 0]
  deltaRotationY = 0  // yaw only — most common use case

  constructor(rootBoneIndex = 0) {
    this.rootBoneIndex = rootBoneIndex
  }

  /**
   * Call after animation sampling but before computeJointMatrices.
   * Extracts root bone movement, zeros it out, and stores the delta.
   */
  extract(skeleton: Skeleton): void {
    const to = this.rootBoneIndex * 3
    const ro = this.rootBoneIndex * 4

    const currentT: Vec3 = [
      skeleton.translations[to],
      skeleton.translations[to + 1],
      skeleton.translations[to + 2],
    ]

    // Compute delta
    this.deltaTranslation = [
      currentT[0] - this.prevTranslation[0],
      currentT[1] - this.prevTranslation[1],
      currentT[2] - this.prevTranslation[2],
    ]

    // Extract yaw rotation delta (simplified)
    const currentR: Quat = [
      skeleton.rotations[ro],
      skeleton.rotations[ro + 1],
      skeleton.rotations[ro + 2],
      skeleton.rotations[ro + 3],
    ]
    const currentYaw = Math.atan2(
      2 * (currentR[3] * currentR[1] + currentR[0] * currentR[2]),
      1 - 2 * (currentR[1] * currentR[1] + currentR[2] * currentR[2])
    )
    const prevYaw = Math.atan2(
      2 * (this.prevRotation[3] * this.prevRotation[1] + this.prevRotation[0] * this.prevRotation[2]),
      1 - 2 * (this.prevRotation[1] * this.prevRotation[1] + this.prevRotation[2] * this.prevRotation[2])
    )
    this.deltaRotationY = currentYaw - prevYaw

    // Store current as previous
    this.prevTranslation = [...currentT]
    this.prevRotation = [...currentR]

    // Zero out root bone XZ translation (keep Y for ground contact)
    skeleton.translations[to] = 0
    skeleton.translations[to + 2] = 0

    // Zero out root yaw rotation
    quat.identity(
      [skeleton.rotations[ro], skeleton.rotations[ro + 1],
       skeleton.rotations[ro + 2], skeleton.rotations[ro + 3]]
    )
    skeleton.rotations[ro] = 0
    skeleton.rotations[ro + 1] = 0
    skeleton.rotations[ro + 2] = 0
    skeleton.rotations[ro + 3] = 1
  }

  /** Reset when animation loops or state changes. */
  reset(skeleton: Skeleton): void {
    const to = this.rootBoneIndex * 3
    const ro = this.rootBoneIndex * 4
    this.prevTranslation = [
      skeleton.translations[to],
      skeleton.translations[to + 1],
      skeleton.translations[to + 2],
    ]
    this.prevRotation = [
      skeleton.rotations[ro],
      skeleton.rotations[ro + 1],
      skeleton.rotations[ro + 2],
      skeleton.rotations[ro + 3],
    ]
    this.deltaTranslation = [0, 0, 0]
    this.deltaRotationY = 0
  }
}
