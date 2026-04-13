/**
 * Physics world — manages bodies, broadphase, narrowphase, solver.
 * Fixed timestep, deterministic accumulator pattern.
 */

import { Vec3, vec3 } from '../math/vec'
import { RigidBody } from './rigidbody'
import { SpatialHashGrid, computeAABB } from './broadphase'
import { narrowphaseTest, ContactInfo } from './gjk'
import { ContactConstraint, createContactConstraint, solveConstraints } from './solver'
import { rayBody, RaycastHit } from './raycast'

export type TriggerCallback = (bodyA: RigidBody, bodyB: RigidBody) => void

export class PhysicsWorld {
  gravity: Vec3 = [0, -9.81, 0]
  solverIterations = 8

  private bodies: RigidBody[] = []
  private broadphase = new SpatialHashGrid(4)
  private contacts: ContactConstraint[] = []

  // Trigger tracking
  private activeTriggers = new Set<string>()
  onTriggerEnter?: TriggerCallback
  onTriggerStay?: TriggerCallback
  onTriggerExit?: TriggerCallback

  // Collision callbacks
  onCollision?: (bodyA: RigidBody, bodyB: RigidBody, contact: ContactInfo) => void

  addBody(body: RigidBody): void {
    this.bodies.push(body)
  }

  removeBody(body: RigidBody): void {
    const idx = this.bodies.indexOf(body)
    if (idx !== -1) {
      this.bodies.splice(idx, 1)
      this.broadphase.remove(body.id)
    }
  }

  getBody(id: number): RigidBody | undefined {
    return this.bodies.find(b => b.id === id)
  }

  get bodyCount(): number {
    return this.bodies.length
  }

  /**
   * Step the physics simulation by dt seconds.
   */
  step(dt: number): void {
    // 1. Integrate velocities only (not positions — solve first)
    for (const body of this.bodies) {
      body.integrateVelocities(dt, this.gravity)
    }

    // 2. Update broadphase (using current positions — pre-move)
    for (const body of this.bodies) {
      const r = body.shape.boundingRadius()
      const maxScale = 1 // no per-body scale in physics
      this.broadphase.insert(body.id, computeAABB(body.position, r * maxScale))
    }

    // 3. Broadphase pair query
    const pairs = this.broadphase.queryPairs()

    // 4. Narrowphase
    this.contacts.length = 0
    const currentTriggers = new Set<string>()

    for (const [idA, idB] of pairs) {
      const bodyA = this.bodies.find(b => b.id === idA)
      const bodyB = this.bodies.find(b => b.id === idB)
      if (!bodyA || !bodyB) continue

      // Skip static-static
      if (bodyA.type === 'static' && bodyB.type === 'static') continue

      const contact = narrowphaseTest(
        bodyA.shape, bodyA.position, bodyA.rotation,
        bodyB.shape, bodyB.position, bodyB.rotation
      )

      if (!contact.colliding) continue

      // Trigger handling
      if (bodyA.isTrigger || bodyB.isTrigger) {
        const key = `${Math.min(idA, idB)}:${Math.max(idA, idB)}`
        currentTriggers.add(key)
        if (!this.activeTriggers.has(key)) {
          this.onTriggerEnter?.(bodyA, bodyB)
        } else {
          this.onTriggerStay?.(bodyA, bodyB)
        }
        continue
      }

      this.onCollision?.(bodyA, bodyB, contact)
      this.contacts.push(createContactConstraint(bodyA, bodyB, contact))
    }

    // Trigger exits
    for (const key of this.activeTriggers) {
      if (!currentTriggers.has(key)) {
        const [idAStr, idBStr] = key.split(':')
        const bodyA = this.bodies.find(b => b.id === parseInt(idAStr))
        const bodyB = this.bodies.find(b => b.id === parseInt(idBStr))
        if (bodyA && bodyB) this.onTriggerExit?.(bodyA, bodyB)
      }
    }
    this.activeTriggers = currentTriggers

    // 5. Solve constraints (adjusts velocities)
    solveConstraints(this.contacts, this.solverIterations)

    // 6. Integrate positions from solved velocities
    for (const body of this.bodies) {
      body.integratePositions(dt)
    }
  }

  /**
   * Raycast against all bodies. Returns closest hit or null.
   */
  raycast(origin: Vec3, direction: Vec3, maxDistance = Infinity): RaycastHit | null {
    const dir = vec3.normalize(vec3.create(), direction)
    let closest: RaycastHit | null = null

    for (const body of this.bodies) {
      const hit = rayBody(origin, dir, body, maxDistance)
      if (hit && (!closest || hit.distance < closest.distance)) {
        closest = hit
        maxDistance = hit.distance
      }
    }

    return closest
  }

  /**
   * Raycast and return ALL hits (sorted by distance).
   */
  raycastAll(origin: Vec3, direction: Vec3, maxDistance = Infinity): RaycastHit[] {
    const dir = vec3.normalize(vec3.create(), direction)
    const hits: RaycastHit[] = []

    for (const body of this.bodies) {
      const hit = rayBody(origin, dir, body, maxDistance)
      if (hit) hits.push(hit)
    }

    return hits.sort((a, b) => a.distance - b.distance)
  }

  /** Clear all bodies and state. */
  clear(): void {
    this.bodies.length = 0
    this.contacts.length = 0
    this.broadphase.clear()
    this.activeTriggers.clear()
  }
}
