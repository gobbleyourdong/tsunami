/**
 * Collision shapes — sphere, box (AABB + OBB), capsule, convex hull.
 * Each shape provides a support function for GJK.
 */

import { Vec3, vec3 } from '../math/vec'
import { Quat, quat } from '../math/quat'

export type ShapeType = 'sphere' | 'box' | 'capsule' | 'convex'

export interface CollisionShape {
  type: ShapeType
  /** GJK support function: farthest point in direction d */
  support(direction: Vec3, position: Vec3, rotation: Quat): Vec3
  /** Bounding sphere radius from origin */
  boundingRadius(): number
}

export class SphereShape implements CollisionShape {
  type: ShapeType = 'sphere'
  constructor(public radius: number) {}

  support(direction: Vec3, position: Vec3): Vec3 {
    const len = vec3.length(direction)
    if (len < 1e-10) return [...position]
    const s = this.radius / len
    return [
      position[0] + direction[0] * s,
      position[1] + direction[1] * s,
      position[2] + direction[2] * s,
    ]
  }

  boundingRadius(): number { return this.radius }
}

export class BoxShape implements CollisionShape {
  type: ShapeType = 'box'
  constructor(public halfExtents: Vec3) {}

  support(direction: Vec3, position: Vec3, rotation: Quat): Vec3 {
    // Rotate direction into local space
    const invRot = quat.create()
    quat.invert(invRot, rotation)
    const localDir = rotateVec3ByQuat([...direction], invRot)

    // Pick farthest corner in local space
    const local: Vec3 = [
      localDir[0] >= 0 ? this.halfExtents[0] : -this.halfExtents[0],
      localDir[1] >= 0 ? this.halfExtents[1] : -this.halfExtents[1],
      localDir[2] >= 0 ? this.halfExtents[2] : -this.halfExtents[2],
    ]

    // Rotate back to world space
    const world = rotateVec3ByQuat(local, rotation)
    return [world[0] + position[0], world[1] + position[1], world[2] + position[2]]
  }

  boundingRadius(): number {
    const h = this.halfExtents
    return Math.sqrt(h[0] * h[0] + h[1] * h[1] + h[2] * h[2])
  }
}

export class CapsuleShape implements CollisionShape {
  type: ShapeType = 'capsule'
  constructor(public radius: number, public halfHeight: number) {}

  support(direction: Vec3, position: Vec3, rotation: Quat): Vec3 {
    const len = vec3.length(direction)
    if (len < 1e-10) return [...position]

    // Local Y axis in world space
    const localUp = rotateVec3ByQuat([0, 1, 0], rotation)

    // Pick top or bottom hemisphere center
    const dot = vec3.dot(direction, localUp)
    const center: Vec3 = [
      position[0] + localUp[0] * (dot >= 0 ? this.halfHeight : -this.halfHeight),
      position[1] + localUp[1] * (dot >= 0 ? this.halfHeight : -this.halfHeight),
      position[2] + localUp[2] * (dot >= 0 ? this.halfHeight : -this.halfHeight),
    ]

    // Extend by radius in direction
    const s = this.radius / len
    return [
      center[0] + direction[0] * s,
      center[1] + direction[1] * s,
      center[2] + direction[2] * s,
    ]
  }

  boundingRadius(): number { return this.halfHeight + this.radius }
}

export class ConvexHullShape implements CollisionShape {
  type: ShapeType = 'convex'
  vertices: Vec3[]

  constructor(vertices: Vec3[]) {
    this.vertices = vertices
  }

  support(direction: Vec3, position: Vec3, rotation: Quat): Vec3 {
    const invRot = quat.create()
    quat.invert(invRot, rotation)
    const localDir = rotateVec3ByQuat([...direction], invRot)

    let bestDot = -Infinity
    let bestVert: Vec3 = this.vertices[0]
    for (const v of this.vertices) {
      const d = v[0] * localDir[0] + v[1] * localDir[1] + v[2] * localDir[2]
      if (d > bestDot) {
        bestDot = d
        bestVert = v
      }
    }

    const world = rotateVec3ByQuat([...bestVert], rotation)
    return [world[0] + position[0], world[1] + position[1], world[2] + position[2]]
  }

  boundingRadius(): number {
    let max = 0
    for (const v of this.vertices) {
      const d = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
      if (d > max) max = d
    }
    return max
  }

  /** Generate convex hull from mesh vertex positions. */
  static fromVertices(positions: Float32Array, stride = 3): ConvexHullShape {
    const verts: Vec3[] = []
    for (let i = 0; i < positions.length; i += stride) {
      verts.push([positions[i], positions[i + 1], positions[i + 2]])
    }
    return new ConvexHullShape(verts)
  }
}

// --- Helpers ---

function rotateVec3ByQuat(v: Vec3, q: Quat): Vec3 {
  const qx = q[0], qy = q[1], qz = q[2], qw = q[3]
  const vx = v[0], vy = v[1], vz = v[2]

  // q * v * q^-1 (optimized)
  const ix = qw * vx + qy * vz - qz * vy
  const iy = qw * vy + qz * vx - qx * vz
  const iz = qw * vz + qx * vy - qy * vx
  const iw = -qx * vx - qy * vy - qz * vz

  return [
    ix * qw + iw * -qx + iy * -qz - iz * -qy,
    iy * qw + iw * -qy + iz * -qx - ix * -qz,
    iz * qw + iw * -qz + ix * -qy - iy * -qx,
  ]
}

export { rotateVec3ByQuat }
