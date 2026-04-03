/**
 * Physics module — public API barrel export.
 */

export { SphereShape, BoxShape, CapsuleShape, ConvexHullShape, rotateVec3ByQuat } from './shapes'
export type { CollisionShape, ShapeType } from './shapes'
export { SpatialHashGrid, aabbOverlap, computeAABB } from './broadphase'
export type { AABB, BroadphaseEntry } from './broadphase'
export { gjkTest, epaContact, narrowphaseTest } from './gjk'
export type { ContactInfo } from './gjk'
export { RigidBody } from './rigidbody'
export type { BodyType } from './rigidbody'
export { solveConstraints, createContactConstraint } from './solver'
export type { ContactConstraint } from './solver'
export { rayAABB, raySphere, rayBody } from './raycast'
export type { RaycastHit } from './raycast'
export { PhysicsWorld } from './world'
export { CharacterController } from './character'
export type { CharacterControllerOptions } from './character'
