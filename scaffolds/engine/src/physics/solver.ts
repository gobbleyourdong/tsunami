/**
 * Constraint solver — sequential impulse (Projected Gauss-Seidel).
 * Resolves contact constraints: non-penetration, friction, restitution.
 */

import { Vec3, vec3 } from '../math/vec'
import { RigidBody } from './rigidbody'
import { ContactInfo } from './gjk'

export interface ContactConstraint {
  bodyA: RigidBody
  bodyB: RigidBody
  contact: ContactInfo
  accumulatedNormalImpulse: number
  accumulatedFrictionImpulse1: number
  accumulatedFrictionImpulse2: number
}

export function createContactConstraint(
  bodyA: RigidBody,
  bodyB: RigidBody,
  contact: ContactInfo
): ContactConstraint {
  return {
    bodyA,
    bodyB,
    contact,
    accumulatedNormalImpulse: 0,
    accumulatedFrictionImpulse1: 0,
    accumulatedFrictionImpulse2: 0,
  }
}

/**
 * Solve contact constraints using sequential impulses.
 * @param constraints Active contact constraints
 * @param iterations Number of solver iterations (8 default)
 */
export function solveConstraints(
  constraints: ContactConstraint[],
  iterations = 8
): void {
  for (let iter = 0; iter < iterations; iter++) {
    for (const c of constraints) {
      solveContact(c)
    }
  }
}

function solveContact(c: ContactConstraint): void {
  const { bodyA, bodyB, contact } = c
  const normal = contact.normal

  // Relative velocity at contact point
  const rA = vec3.sub(vec3.create(), contact.pointA, bodyA.position)
  const rB = vec3.sub(vec3.create(), contact.pointB, bodyB.position)

  const velA = vec3.add(vec3.create(), bodyA.velocity,
    vec3.cross(vec3.create(), bodyA.angularVelocity, rA))
  const velB = vec3.add(vec3.create(), bodyB.velocity,
    vec3.cross(vec3.create(), bodyB.angularVelocity, rB))

  // relVel = vB - vA (standard convention: negative = approaching)
  const relVel = vec3.sub(vec3.create(), velB, velA)
  const relVelNormal = vec3.dot(relVel, normal)

  // Already separating
  if (relVelNormal > 0) return

  // Effective mass along normal
  const rAxN = vec3.cross(vec3.create(), rA, normal)
  const rBxN = vec3.cross(vec3.create(), rB, normal)

  const effectiveMass =
    bodyA.inverseMass + bodyB.inverseMass +
    vec3.dot(rAxN, rAxN) * bodyA.inverseInertia +
    vec3.dot(rBxN, rBxN) * bodyB.inverseInertia

  if (effectiveMass <= 0) return

  // Restitution
  const restitution = Math.max(bodyA.restitution, bodyB.restitution)
  const velocityBias = -restitution * relVelNormal

  // Baumgarte stabilization: push objects apart based on penetration
  const biasFactor = 0.2
  const slop = 0.005
  const penetrationBias = (biasFactor / (1 / 60)) * Math.max(contact.depth - slop, 0)

  // Normal impulse
  let lambda = -(relVelNormal + velocityBias + penetrationBias) / effectiveMass

  // Clamp accumulated impulse (non-negative — can only push apart)
  const oldAccum = c.accumulatedNormalImpulse
  c.accumulatedNormalImpulse = Math.max(0, oldAccum + lambda)
  lambda = c.accumulatedNormalImpulse - oldAccum

  const impulse: Vec3 = [
    normal[0] * lambda,
    normal[1] * lambda,
    normal[2] * lambda,
  ]

  // Apply impulse: A gets -impulse (pushed away from B), B gets +impulse
  if (bodyA.type === 'dynamic') {
    bodyA.velocity[0] -= impulse[0] * bodyA.inverseMass
    bodyA.velocity[1] -= impulse[1] * bodyA.inverseMass
    bodyA.velocity[2] -= impulse[2] * bodyA.inverseMass
    const angA = vec3.cross(vec3.create(), rA, impulse)
    bodyA.angularVelocity[0] -= angA[0] * bodyA.inverseInertia
    bodyA.angularVelocity[1] -= angA[1] * bodyA.inverseInertia
    bodyA.angularVelocity[2] -= angA[2] * bodyA.inverseInertia
  }

  if (bodyB.type === 'dynamic') {
    bodyB.velocity[0] += impulse[0] * bodyB.inverseMass
    bodyB.velocity[1] += impulse[1] * bodyB.inverseMass
    bodyB.velocity[2] += impulse[2] * bodyB.inverseMass
    const angB = vec3.cross(vec3.create(), rB, impulse)
    bodyB.angularVelocity[0] += angB[0] * bodyB.inverseInertia
    bodyB.angularVelocity[1] += angB[1] * bodyB.inverseInertia
    bodyB.angularVelocity[2] += angB[2] * bodyB.inverseInertia
  }

  // --- Friction ---
  solveFriction(c, rA, rB, effectiveMass)
}

function solveFriction(
  c: ContactConstraint,
  rA: Vec3, rB: Vec3,
  normalEffectiveMass: number
): void {
  const { bodyA, bodyB, contact } = c
  const normal = contact.normal

  // Recompute relative velocity (vB - vA)
  const velA = vec3.add(vec3.create(), bodyA.velocity,
    vec3.cross(vec3.create(), bodyA.angularVelocity, rA))
  const velB = vec3.add(vec3.create(), bodyB.velocity,
    vec3.cross(vec3.create(), bodyB.angularVelocity, rB))
  const relVel = vec3.sub(vec3.create(), velB, velA)

  // Tangent velocity
  const relVelNormal = vec3.dot(relVel, normal)
  const tangent: Vec3 = [
    relVel[0] - normal[0] * relVelNormal,
    relVel[1] - normal[1] * relVelNormal,
    relVel[2] - normal[2] * relVelNormal,
  ]
  const tangentLen = vec3.length(tangent)
  if (tangentLen < 1e-8) return

  vec3.scale(tangent, tangent, 1 / tangentLen)

  const tangentVel = vec3.dot(relVel, tangent)
  const friction = Math.sqrt(bodyA.friction * bodyB.friction)
  const maxFriction = c.accumulatedNormalImpulse * friction

  let frictionLambda = -tangentVel / normalEffectiveMass

  const oldAccum = c.accumulatedFrictionImpulse1
  c.accumulatedFrictionImpulse1 = Math.max(-maxFriction, Math.min(maxFriction, oldAccum + frictionLambda))
  frictionLambda = c.accumulatedFrictionImpulse1 - oldAccum

  const frictionImpulse: Vec3 = [
    tangent[0] * frictionLambda,
    tangent[1] * frictionLambda,
    tangent[2] * frictionLambda,
  ]

  if (bodyA.type === 'dynamic') {
    bodyA.velocity[0] -= frictionImpulse[0] * bodyA.inverseMass
    bodyA.velocity[1] -= frictionImpulse[1] * bodyA.inverseMass
    bodyA.velocity[2] -= frictionImpulse[2] * bodyA.inverseMass
  }
  if (bodyB.type === 'dynamic') {
    bodyB.velocity[0] += frictionImpulse[0] * bodyB.inverseMass
    bodyB.velocity[1] += frictionImpulse[1] * bodyB.inverseMass
    bodyB.velocity[2] += frictionImpulse[2] * bodyB.inverseMass
  }
}
