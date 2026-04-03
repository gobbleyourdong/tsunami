/**
 * Raycasting + shape casting against physics world.
 * Tests ray against AABBs (broadphase) then shapes (narrowphase).
 */

import { Vec3, vec3 } from '../math/vec'
import { Quat } from '../math/quat'
import { AABB } from './broadphase'
import { CollisionShape, SphereShape, BoxShape } from './shapes'
import { rotateVec3ByQuat } from './shapes'
import { RigidBody } from './rigidbody'

export interface RaycastHit {
  body: RigidBody
  point: Vec3
  normal: Vec3
  distance: number
}

/**
 * Test ray against AABB (slab method).
 */
export function rayAABB(
  origin: Vec3, direction: Vec3, aabb: AABB
): { hit: boolean; tMin: number } {
  let tMin = -Infinity
  let tMax = Infinity

  for (let i = 0; i < 3; i++) {
    if (Math.abs(direction[i]) < 1e-10) {
      if (origin[i] < aabb.min[i] || origin[i] > aabb.max[i]) {
        return { hit: false, tMin: 0 }
      }
    } else {
      const invD = 1 / direction[i]
      let t1 = (aabb.min[i] - origin[i]) * invD
      let t2 = (aabb.max[i] - origin[i]) * invD
      if (t1 > t2) { const tmp = t1; t1 = t2; t2 = tmp }
      tMin = Math.max(tMin, t1)
      tMax = Math.min(tMax, t2)
      if (tMin > tMax) return { hit: false, tMin: 0 }
    }
  }

  return { hit: tMax >= 0, tMin: Math.max(0, tMin) }
}

/**
 * Test ray against sphere.
 */
export function raySphere(
  origin: Vec3, direction: Vec3, center: Vec3, radius: number
): { hit: boolean; distance: number; point: Vec3; normal: Vec3 } {
  const oc = vec3.sub(vec3.create(), origin, center)
  const a = vec3.dot(direction, direction)
  const b = 2 * vec3.dot(oc, direction)
  const c = vec3.dot(oc, oc) - radius * radius
  const disc = b * b - 4 * a * c

  if (disc < 0) {
    return { hit: false, distance: 0, point: [0, 0, 0], normal: [0, 0, 0] }
  }

  const t = (-b - Math.sqrt(disc)) / (2 * a)
  if (t < 0) {
    return { hit: false, distance: 0, point: [0, 0, 0], normal: [0, 0, 0] }
  }

  const point: Vec3 = [
    origin[0] + direction[0] * t,
    origin[1] + direction[1] * t,
    origin[2] + direction[2] * t,
  ]
  const normal = vec3.normalize(vec3.create(), vec3.sub(vec3.create(), point, center))

  return { hit: true, distance: t, point, normal }
}

/**
 * Test ray against a rigidbody's shape (dispatches by shape type).
 */
export function rayBody(
  origin: Vec3, direction: Vec3, body: RigidBody, maxDistance = Infinity
): RaycastHit | null {
  // Quick AABB pre-check
  const r = body.shape.boundingRadius()
  const aabb: AABB = {
    min: [body.position[0] - r, body.position[1] - r, body.position[2] - r],
    max: [body.position[0] + r, body.position[1] + r, body.position[2] + r],
  }
  const { hit: aabbHit, tMin } = rayAABB(origin, direction, aabb)
  if (!aabbHit || tMin > maxDistance) return null

  if (body.shape.type === 'sphere') {
    const sphere = body.shape as SphereShape
    const result = raySphere(origin, direction, body.position, sphere.radius)
    if (result.hit && result.distance <= maxDistance) {
      return { body, point: result.point, normal: result.normal, distance: result.distance }
    }
  } else if (body.shape.type === 'box') {
    // Transform ray into box local space
    const box = body.shape as BoxShape
    const invRot: Quat = [0, 0, 0, 1]
    const q = body.rotation
    // Invert quaternion
    const len = q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]
    const inv = len > 0 ? 1 / len : 0
    invRot[0] = -q[0] * inv; invRot[1] = -q[1] * inv
    invRot[2] = -q[2] * inv; invRot[3] = q[3] * inv

    const localOrigin = rotateVec3ByQuat(
      vec3.sub(vec3.create(), origin, body.position),
      invRot
    )
    const localDir = rotateVec3ByQuat([...direction], invRot)

    const localAABB: AABB = {
      min: [-box.halfExtents[0], -box.halfExtents[1], -box.halfExtents[2]],
      max: [box.halfExtents[0], box.halfExtents[1], box.halfExtents[2]],
    }

    const result = rayAABB(localOrigin, localDir, localAABB)
    if (result.hit && result.tMin <= maxDistance) {
      const localPoint: Vec3 = [
        localOrigin[0] + localDir[0] * result.tMin,
        localOrigin[1] + localDir[1] * result.tMin,
        localOrigin[2] + localDir[2] * result.tMin,
      ]

      // Compute normal from which face was hit
      let localNormal: Vec3 = [0, 0, 0]
      let minDist = Infinity
      for (let i = 0; i < 3; i++) {
        const dPos = Math.abs(localPoint[i] - box.halfExtents[i])
        const dNeg = Math.abs(localPoint[i] + box.halfExtents[i])
        if (dPos < minDist) { minDist = dPos; localNormal = [0, 0, 0]; localNormal[i] = 1 }
        if (dNeg < minDist) { minDist = dNeg; localNormal = [0, 0, 0]; localNormal[i] = -1 }
      }

      const worldPoint = vec3.add(vec3.create(),
        rotateVec3ByQuat(localPoint, body.rotation), body.position)
      const worldNormal = rotateVec3ByQuat(localNormal, body.rotation)

      return { body, point: worldPoint, normal: worldNormal, distance: result.tMin }
    }
  } else {
    // Fallback: use bounding sphere for convex/capsule
    const result = raySphere(origin, direction, body.position, r)
    if (result.hit && result.distance <= maxDistance) {
      return { body, point: result.point, normal: result.normal, distance: result.distance }
    }
  }

  return null
}
