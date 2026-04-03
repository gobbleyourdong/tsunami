/**
 * Rigidbody — position, velocity, angular velocity, mass, inertia tensor.
 * Integrates forces and torques. Used by the physics world solver.
 */

import { Vec3, vec3 } from '../math/vec'
import { Quat, quat } from '../math/quat'
import { CollisionShape } from './shapes'

export type BodyType = 'dynamic' | 'kinematic' | 'static'

export class RigidBody {
  readonly id: number
  type: BodyType

  // Transform
  position: Vec3
  rotation: Quat
  previousPosition: Vec3

  // Dynamics
  velocity: Vec3 = [0, 0, 0]
  angularVelocity: Vec3 = [0, 0, 0]

  // Mass properties
  mass: number
  inverseMass: number
  inertia: number       // simplified scalar inertia
  inverseInertia: number

  // Material
  restitution = 0.3
  friction = 0.5

  // Collision
  shape: CollisionShape
  isTrigger = false

  // Accumulated forces (reset each step)
  force: Vec3 = [0, 0, 0]
  torque: Vec3 = [0, 0, 0]

  // Damping
  linearDamping = 0.01
  angularDamping = 0.05

  // Sleep
  sleeping = false
  sleepTimer = 0

  // User data
  userData: unknown = null

  private static nextId = 0

  constructor(shape: CollisionShape, options?: {
    type?: BodyType
    mass?: number
    position?: Vec3
    rotation?: Quat
    restitution?: number
    friction?: number
    isTrigger?: boolean
  }) {
    this.id = RigidBody.nextId++
    this.shape = shape
    this.type = options?.type ?? 'dynamic'
    this.position = options?.position ?? [0, 0, 0]
    this.previousPosition = [...this.position]
    this.rotation = options?.rotation ?? [0, 0, 0, 1]
    this.restitution = options?.restitution ?? 0.3
    this.friction = options?.friction ?? 0.5
    this.isTrigger = options?.isTrigger ?? false

    const m = this.type === 'dynamic' ? (options?.mass ?? 1.0) : 0
    this.mass = m
    this.inverseMass = m > 0 ? 1 / m : 0
    // Simplified inertia: 2/5 * m * r^2 (sphere approximation)
    const r = shape.boundingRadius()
    this.inertia = m > 0 ? 0.4 * m * r * r : 0
    this.inverseInertia = this.inertia > 0 ? 1 / this.inertia : 0
  }

  applyForce(force: Vec3): void {
    this.force[0] += force[0]
    this.force[1] += force[1]
    this.force[2] += force[2]
    this.wake()
  }

  applyImpulse(impulse: Vec3): void {
    this.velocity[0] += impulse[0] * this.inverseMass
    this.velocity[1] += impulse[1] * this.inverseMass
    this.velocity[2] += impulse[2] * this.inverseMass
    this.wake()
  }

  applyTorque(torque: Vec3): void {
    this.torque[0] += torque[0]
    this.torque[1] += torque[1]
    this.torque[2] += torque[2]
    this.wake()
  }

  applyImpulseAtPoint(impulse: Vec3, point: Vec3): void {
    this.applyImpulse(impulse)
    const r = vec3.sub(vec3.create(), point, this.position)
    const torque = vec3.cross(vec3.create(), r, impulse)
    this.angularVelocity[0] += torque[0] * this.inverseInertia
    this.angularVelocity[1] += torque[1] * this.inverseInertia
    this.angularVelocity[2] += torque[2] * this.inverseInertia
    this.wake()
  }

  /** Phase 1: Integrate forces → update velocities only (before solve). */
  integrateVelocities(dt: number, gravity: Vec3): void {
    if (this.type !== 'dynamic' || this.sleeping) return

    this.previousPosition = [...this.position]

    // Apply gravity + accumulated forces
    this.velocity[0] += (gravity[0] + this.force[0] * this.inverseMass) * dt
    this.velocity[1] += (gravity[1] + this.force[1] * this.inverseMass) * dt
    this.velocity[2] += (gravity[2] + this.force[2] * this.inverseMass) * dt

    // Angular acceleration
    this.angularVelocity[0] += this.torque[0] * this.inverseInertia * dt
    this.angularVelocity[1] += this.torque[1] * this.inverseInertia * dt
    this.angularVelocity[2] += this.torque[2] * this.inverseInertia * dt

    // Damping
    const ld = Math.pow(1 - this.linearDamping, dt)
    const ad = Math.pow(1 - this.angularDamping, dt)
    vec3.scale(this.velocity, this.velocity, ld)
    vec3.scale(this.angularVelocity, this.angularVelocity, ad)

    // Clear forces
    this.force = [0, 0, 0]
    this.torque = [0, 0, 0]
  }

  /** Phase 2: Integrate positions from (solved) velocities (after solve). */
  integratePositions(dt: number): void {
    if (this.type !== 'dynamic' || this.sleeping) return

    this.position[0] += this.velocity[0] * dt
    this.position[1] += this.velocity[1] * dt
    this.position[2] += this.velocity[2] * dt

    // Rotation update
    const angLen = vec3.length(this.angularVelocity)
    if (angLen > 1e-8) {
      const halfAngle = angLen * dt * 0.5
      const s = Math.sin(halfAngle) / angLen
      const dq: Quat = [
        this.angularVelocity[0] * s,
        this.angularVelocity[1] * s,
        this.angularVelocity[2] * s,
        Math.cos(halfAngle),
      ]
      quat.multiply(this.rotation, dq, this.rotation)
      quat.normalize(this.rotation, this.rotation)
    }

    // Sleep check
    const speed = vec3.length(this.velocity) + vec3.length(this.angularVelocity)
    if (speed < 0.01) {
      this.sleepTimer += dt
      if (this.sleepTimer > 1.0) this.sleeping = true
    } else {
      this.sleepTimer = 0
    }
  }

  /** Combined integrate (for backwards compat — integrates both phases). */
  integrate(dt: number, gravity: Vec3): void {
    this.integrateVelocities(dt, gravity)
    this.integratePositions(dt)
  }

  wake(): void {
    this.sleeping = false
    this.sleepTimer = 0
  }
}
