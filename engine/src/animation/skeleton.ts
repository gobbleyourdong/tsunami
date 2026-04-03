/**
 * Skeleton and bone hierarchy for skeletal animation.
 * Stores bind pose, computes joint matrices for skinning.
 */

import { Quat, quat } from '../math/quat'
import { Vec3, mat4 } from '../math/vec'

export interface BonePose {
  translation: Vec3
  rotation: Quat
  scale: Vec3
}

export class Skeleton {
  readonly boneCount: number
  readonly names: string[]
  readonly parents: Int32Array  // -1 = root
  readonly inverseBindMatrices: Float32Array  // boneCount * 16

  // Current pose (local space)
  translations: Float32Array  // boneCount * 3
  rotations: Float32Array     // boneCount * 4
  scales: Float32Array        // boneCount * 3

  // Computed joint matrices (world space * inverse bind)
  jointMatrices: Float32Array  // boneCount * 16 — ready for GPU upload

  // Intermediate world matrices
  private worldMatrices: Float32Array  // boneCount * 16

  constructor(
    names: string[],
    parents: Int32Array,
    inverseBindMatrices: Float32Array,
    restPose?: { translations: Float32Array; rotations: Float32Array; scales: Float32Array }
  ) {
    this.boneCount = names.length
    this.names = names
    this.parents = parents
    this.inverseBindMatrices = inverseBindMatrices

    // Initialize to rest pose or identity
    this.translations = restPose?.translations ?? new Float32Array(this.boneCount * 3)
    this.rotations = restPose?.rotations ?? new Float32Array(this.boneCount * 4)
    this.scales = restPose?.scales ?? new Float32Array(this.boneCount * 3)

    // Default identity rotations and unit scales
    if (!restPose) {
      for (let i = 0; i < this.boneCount; i++) {
        this.rotations[i * 4 + 3] = 1  // w = 1
        this.scales[i * 3 + 0] = 1
        this.scales[i * 3 + 1] = 1
        this.scales[i * 3 + 2] = 1
      }
    }

    this.jointMatrices = new Float32Array(this.boneCount * 16)
    this.worldMatrices = new Float32Array(this.boneCount * 16)
  }

  /** Set a bone's local pose. */
  setBonePose(boneIndex: number, pose: Partial<BonePose>): void {
    if (pose.translation) {
      const o = boneIndex * 3
      this.translations[o] = pose.translation[0]
      this.translations[o + 1] = pose.translation[1]
      this.translations[o + 2] = pose.translation[2]
    }
    if (pose.rotation) {
      const o = boneIndex * 4
      this.rotations[o] = pose.rotation[0]
      this.rotations[o + 1] = pose.rotation[1]
      this.rotations[o + 2] = pose.rotation[2]
      this.rotations[o + 3] = pose.rotation[3]
    }
    if (pose.scale) {
      const o = boneIndex * 3
      this.scales[o] = pose.scale[0]
      this.scales[o + 1] = pose.scale[1]
      this.scales[o + 2] = pose.scale[2]
    }
  }

  /** Get bone index by name. Returns -1 if not found. */
  getBoneIndex(name: string): number {
    return this.names.indexOf(name)
  }

  /**
   * Compute joint matrices from current pose.
   * Must be called after animation sampling before rendering.
   */
  computeJointMatrices(): void {
    const local = mat4.create()
    const rotMat = new Float32Array(16)

    for (let i = 0; i < this.boneCount; i++) {
      const to = i * 3
      const ro = i * 4
      const so = i * 3

      // Build local matrix: T * R * S
      const q: Quat = [
        this.rotations[ro],
        this.rotations[ro + 1],
        this.rotations[ro + 2],
        this.rotations[ro + 3],
      ]
      quat.toMat4(rotMat, q)

      // Apply translation
      rotMat[12] = this.translations[to]
      rotMat[13] = this.translations[to + 1]
      rotMat[14] = this.translations[to + 2]

      // Apply scale
      rotMat[0] *= this.scales[so]; rotMat[1] *= this.scales[so]; rotMat[2] *= this.scales[so]
      rotMat[4] *= this.scales[so + 1]; rotMat[5] *= this.scales[so + 1]; rotMat[6] *= this.scales[so + 1]
      rotMat[8] *= this.scales[so + 2]; rotMat[9] *= this.scales[so + 2]; rotMat[10] *= this.scales[so + 2]

      // World = parent.world * local
      const wo = i * 16
      const parentIdx = this.parents[i]
      if (parentIdx < 0) {
        this.worldMatrices.set(rotMat, wo)
      } else {
        const po = parentIdx * 16
        mat4.multiply(
          this.worldMatrices.subarray(wo, wo + 16) as unknown as Float32Array,
          this.worldMatrices.subarray(po, po + 16) as unknown as Float32Array,
          rotMat
        )
      }

      // Joint matrix = world * inverseBindMatrix
      const ibo = i * 16
      mat4.multiply(
        this.jointMatrices.subarray(wo, wo + 16) as unknown as Float32Array,
        this.worldMatrices.subarray(wo, wo + 16) as unknown as Float32Array,
        this.inverseBindMatrices.subarray(ibo, ibo + 16) as unknown as Float32Array
      )
    }
  }

  /** Get the world-space position of a bone (after computeJointMatrices). */
  getBoneWorldPosition(boneIndex: number): Vec3 {
    const o = boneIndex * 16
    return [this.worldMatrices[o + 12], this.worldMatrices[o + 13], this.worldMatrices[o + 14]]
  }
}
