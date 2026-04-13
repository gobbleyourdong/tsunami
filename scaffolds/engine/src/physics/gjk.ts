/**
 * GJK (Gilbert-Johnson-Keerthi) + EPA (Expanding Polytope Algorithm).
 * Narrowphase collision detection for arbitrary convex shapes.
 */

import { Vec3, vec3 } from '../math/vec'
import { Quat } from '../math/quat'
import { CollisionShape } from './shapes'

export interface ContactInfo {
  colliding: boolean
  normal: Vec3      // contact normal (from A to B)
  depth: number     // penetration depth
  pointA: Vec3      // contact point on A
  pointB: Vec3      // contact point on B
}

const NO_CONTACT: ContactInfo = {
  colliding: false,
  normal: [0, 0, 0],
  depth: 0,
  pointA: [0, 0, 0],
  pointB: [0, 0, 0],
}

function minkowskiSupport(
  shapeA: CollisionShape, posA: Vec3, rotA: Quat,
  shapeB: CollisionShape, posB: Vec3, rotB: Quat,
  direction: Vec3
): Vec3 {
  const a = shapeA.support(direction, posA, rotA)
  const negDir: Vec3 = [-direction[0], -direction[1], -direction[2]]
  const b = shapeB.support(negDir, posB, rotB)
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}

function tripleProduct(a: Vec3, b: Vec3, c: Vec3): Vec3 {
  // (a × b) × c = b(c·a) - a(c·b)
  const ca = vec3.dot(c, a)
  const cb = vec3.dot(c, b)
  return [b[0] * ca - a[0] * cb, b[1] * ca - a[1] * cb, b[2] * ca - a[2] * cb]
}

/**
 * GJK collision test between two convex shapes.
 */
export function gjkTest(
  shapeA: CollisionShape, posA: Vec3, rotA: Quat,
  shapeB: CollisionShape, posB: Vec3, rotB: Quat
): { colliding: boolean; simplex: Vec3[] } {
  // Initial direction: from A to B
  let direction: Vec3 = [posB[0] - posA[0], posB[1] - posA[1], posB[2] - posA[2]]
  if (vec3.length(direction) < 1e-10) direction = [1, 0, 0]

  const simplex: Vec3[] = []
  const a = minkowskiSupport(shapeA, posA, rotA, shapeB, posB, rotB, direction)
  simplex.push(a)

  direction = [-a[0], -a[1], -a[2]]

  for (let iter = 0; iter < 64; iter++) {
    const newPoint = minkowskiSupport(shapeA, posA, rotA, shapeB, posB, rotB, direction)

    if (vec3.dot(newPoint, direction) < 0) {
      return { colliding: false, simplex }
    }

    simplex.push(newPoint)

    if (simplex.length === 2) {
      // Line case
      const b = simplex[0]
      const ab = vec3.sub(vec3.create(), b, a)
      const ao: Vec3 = [-newPoint[0], -newPoint[1], -newPoint[2]]
      direction = tripleProduct(ab, ao, ab)
      if (vec3.length(direction) < 1e-10) {
        // Degenerate — pick perpendicular
        direction = Math.abs(ab[0]) > 0.9 ? [0, 1, 0] : [1, 0, 0]
        direction = vec3.cross(vec3.create(), ab, direction)
      }
    } else if (simplex.length === 3) {
      // Triangle case
      const c = simplex[0], b = simplex[1]
      const ab = vec3.sub(vec3.create(), b, newPoint)
      const ac = vec3.sub(vec3.create(), c, newPoint)
      const ao: Vec3 = [-newPoint[0], -newPoint[1], -newPoint[2]]
      const abc = vec3.cross(vec3.create(), ab, ac)

      const abPerp = vec3.cross(vec3.create(), ab, abc)
      const acPerp = vec3.cross(vec3.create(), abc, ac)

      if (vec3.dot(acPerp, ao) > 0) {
        // Region AC
        simplex.splice(1, 1) // remove b
        direction = tripleProduct(ac, ao, ac)
      } else if (vec3.dot(abPerp, ao) > 0) {
        // Region AB
        simplex.splice(0, 1) // remove c
        direction = tripleProduct(ab, ao, ab)
      } else {
        // Inside triangle — need tetrahedron
        if (vec3.dot(abc, ao) > 0) {
          direction = [...abc]
        } else {
          // Flip winding
          const tmp = simplex[0]
          simplex[0] = simplex[1]
          simplex[1] = tmp
          direction = [-abc[0], -abc[1], -abc[2]]
        }
      }
    } else if (simplex.length === 4) {
      // Tetrahedron case
      const result = doTetrahedron(simplex, direction)
      if (result === true) return { colliding: true, simplex }
      direction = result as Vec3
    }
  }

  return { colliding: false, simplex }
}

function doTetrahedron(simplex: Vec3[], direction: Vec3): true | Vec3 {
  const a = simplex[3] // newest point
  const b = simplex[2]
  const c = simplex[1]
  const d = simplex[0]

  const ab = vec3.sub(vec3.create(), b, a)
  const ac = vec3.sub(vec3.create(), c, a)
  const ad = vec3.sub(vec3.create(), d, a)
  const ao: Vec3 = [-a[0], -a[1], -a[2]]

  const abc = vec3.cross(vec3.create(), ab, ac)
  const acd = vec3.cross(vec3.create(), ac, ad)
  const adb = vec3.cross(vec3.create(), ad, ab)

  if (vec3.dot(abc, ao) > 0) {
    simplex.splice(0, 1) // remove d
    return [...abc] as Vec3
  }
  if (vec3.dot(acd, ao) > 0) {
    simplex.splice(2, 1) // remove b
    return [...acd] as Vec3
  }
  if (vec3.dot(adb, ao) > 0) {
    simplex.splice(1, 1) // remove c
    return [...adb] as Vec3
  }

  return true // origin inside tetrahedron
}

/**
 * EPA: compute penetration depth and contact normal after GJK confirms collision.
 * Simplified — returns approximate normal and depth.
 */
export function epaContact(
  shapeA: CollisionShape, posA: Vec3, rotA: Quat,
  shapeB: CollisionShape, posB: Vec3, rotB: Quat,
  simplex: Vec3[]
): ContactInfo {
  // Expand simplex to tetrahedron if needed
  while (simplex.length < 4) {
    const dir: Vec3 = simplex.length === 1
      ? [1, 0, 0]
      : simplex.length === 2
        ? vec3.cross(vec3.create(),
            vec3.sub(vec3.create(), simplex[1], simplex[0]),
            [0, 1, 0])
        : vec3.cross(vec3.create(),
            vec3.sub(vec3.create(), simplex[1], simplex[0]),
            vec3.sub(vec3.create(), simplex[2], simplex[0]))
    if (vec3.length(dir) < 1e-10) {
      dir[0] = 1; dir[1] = 0; dir[2] = 0
    }
    simplex.push(minkowskiSupport(shapeA, posA, rotA, shapeB, posB, rotB, dir))
  }

  interface Face { a: number; b: number; c: number; normal: Vec3; dist: number }
  const points = [...simplex]
  const faces: Face[] = []

  const addFace = (a: number, b: number, c: number) => {
    const ab = vec3.sub(vec3.create(), points[b], points[a])
    const ac = vec3.sub(vec3.create(), points[c], points[a])
    let normal = vec3.cross(vec3.create(), ab, ac)
    const len = vec3.length(normal)
    if (len < 1e-10) return
    vec3.scale(normal, normal, 1 / len)
    const dist = vec3.dot(normal, points[a])
    if (dist < 0) {
      normal = [-normal[0], -normal[1], -normal[2]]
      faces.push({ a: c, b, c: a, normal, dist: -dist })
    } else {
      faces.push({ a, b, c, normal, dist })
    }
  }

  addFace(0, 1, 2); addFace(0, 2, 3); addFace(0, 3, 1); addFace(1, 3, 2)

  for (let iter = 0; iter < 32; iter++) {
    if (faces.length === 0) break

    // Find closest face to origin
    let minDist = Infinity
    let minIdx = 0
    for (let i = 0; i < faces.length; i++) {
      if (faces[i].dist < minDist) {
        minDist = faces[i].dist
        minIdx = i
      }
    }

    const closest = faces[minIdx]
    const newPoint = minkowskiSupport(
      shapeA, posA, rotA, shapeB, posB, rotB, closest.normal
    )
    const newDist = vec3.dot(newPoint, closest.normal)

    if (newDist - minDist < 0.001) {
      // Converged
      const midpoint: Vec3 = [
        (posA[0] + posB[0]) * 0.5,
        (posA[1] + posB[1]) * 0.5,
        (posA[2] + posB[2]) * 0.5,
      ]
      return {
        colliding: true,
        normal: closest.normal,
        depth: minDist,
        pointA: [
          midpoint[0] + closest.normal[0] * minDist * 0.5,
          midpoint[1] + closest.normal[1] * minDist * 0.5,
          midpoint[2] + closest.normal[2] * minDist * 0.5,
        ],
        pointB: [
          midpoint[0] - closest.normal[0] * minDist * 0.5,
          midpoint[1] - closest.normal[1] * minDist * 0.5,
          midpoint[2] - closest.normal[2] * minDist * 0.5,
        ],
      }
    }

    // Expand polytope
    const newIdx = points.length
    points.push(newPoint)

    // Remove faces visible from new point and add new faces
    const edges: [number, number][] = []
    const remaining: Face[] = []

    for (const face of faces) {
      if (vec3.dot(face.normal, vec3.sub(vec3.create(), newPoint, points[face.a])) > 0) {
        // Visible — collect edges
        const addEdge = (a: number, b: number) => {
          const existing = edges.findIndex(e => e[0] === b && e[1] === a)
          if (existing !== -1) edges.splice(existing, 1)
          else edges.push([a, b])
        }
        addEdge(face.a, face.b)
        addEdge(face.b, face.c)
        addEdge(face.c, face.a)
      } else {
        remaining.push(face)
      }
    }

    faces.length = 0
    faces.push(...remaining)
    for (const [a, b] of edges) {
      addFace(a, b, newIdx)
    }
  }

  // Fallback: use direction between centers
  const dir = vec3.normalize(vec3.create(), vec3.sub(vec3.create(), posB, posA))
  if (vec3.length(dir) < 1e-10) dir[1] = 1
  return {
    colliding: true,
    normal: dir,
    depth: 0.01,
    pointA: [...posA],
    pointB: [...posB],
  }
}

/**
 * Full narrowphase test: GJK + EPA.
 */
export function narrowphaseTest(
  shapeA: CollisionShape, posA: Vec3, rotA: Quat,
  shapeB: CollisionShape, posB: Vec3, rotB: Quat
): ContactInfo {
  const { colliding, simplex } = gjkTest(shapeA, posA, rotA, shapeB, posB, rotB)
  if (!colliding) return NO_CONTACT
  return epaContact(shapeA, posA, rotA, shapeB, posB, rotB, simplex)
}
