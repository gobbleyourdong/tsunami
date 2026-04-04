/**
 * Character controller — kinematic body with sweep tests.
 * Slope limits, step height, ground snap, slide along walls.
 */

import { Vec3, vec3 } from '../math/vec'
import { PhysicsWorld } from './world'
import { RigidBody } from './rigidbody'
import { CapsuleShape } from './shapes'

export interface CharacterControllerOptions {
  radius?: number
  height?: number
  stepHeight?: number
  slopeLimit?: number    // max walkable slope in degrees
  groundSnap?: number    // distance to snap to ground
  skinWidth?: number     // collision skin thickness
}

export class CharacterController {
  body: RigidBody
  velocity: Vec3 = [0, 0, 0]

  isGrounded = false
  groundNormal: Vec3 = [0, 1, 0]

  readonly stepHeight: number
  readonly slopeLimit: number
  readonly groundSnap: number
  readonly skinWidth: number

  private world: PhysicsWorld

  constructor(world: PhysicsWorld, position: Vec3, options?: CharacterControllerOptions) {
    this.world = world
    const radius = options?.radius ?? 0.3
    const height = options?.height ?? 1.8
    const halfHeight = (height - radius * 2) / 2

    this.body = new RigidBody(
      new CapsuleShape(radius, Math.max(0, halfHeight)),
      { type: 'kinematic', position, mass: 0 }
    )
    this.world.addBody(this.body)

    this.stepHeight = options?.stepHeight ?? 0.3
    this.slopeLimit = (options?.slopeLimit ?? 45) * Math.PI / 180
    this.groundSnap = options?.groundSnap ?? 0.1
    this.skinWidth = options?.skinWidth ?? 0.01
  }

  get position(): Vec3 {
    return this.body.position
  }

  set position(pos: Vec3) {
    this.body.position = [...pos]
  }

  /**
   * Move the character by a desired displacement.
   * Handles ground detection, slope limits, and wall sliding.
   */
  move(displacement: Vec3, dt: number): void {
    // Ground check via downward raycast
    const feetPos: Vec3 = [
      this.body.position[0],
      this.body.position[1] - this.body.shape.boundingRadius(),
      this.body.position[2],
    ]
    const groundHit = this.world.raycast(
      [feetPos[0], feetPos[1] + 0.1, feetPos[2]],
      [0, -1, 0],
      this.groundSnap + 0.2
    )

    if (groundHit && groundHit.body !== this.body) {
      const slopeAngle = Math.acos(Math.min(1, vec3.dot(groundHit.normal, [0, 1, 0])))
      this.isGrounded = slopeAngle <= this.slopeLimit
      this.groundNormal = groundHit.normal

      // Snap to ground
      if (this.isGrounded && groundHit.distance < this.groundSnap + 0.1) {
        const snapY = groundHit.point[1] + this.body.shape.boundingRadius()
        if (this.body.position[1] - snapY < this.groundSnap) {
          this.body.position[1] = snapY
        }
      }
    } else {
      this.isGrounded = false
      this.groundNormal = [0, 1, 0]
    }

    // Project movement onto ground plane if grounded
    let finalDisp: Vec3 = [...displacement]
    if (this.isGrounded && displacement[1] <= 0) {
      // Slide along ground slope
      const dot = vec3.dot(displacement, this.groundNormal)
      finalDisp = [
        displacement[0] - this.groundNormal[0] * dot,
        displacement[1] - this.groundNormal[1] * dot,
        displacement[2] - this.groundNormal[2] * dot,
      ]
    }

    // Apply displacement
    this.body.position[0] += finalDisp[0]
    this.body.position[1] += finalDisp[1]
    this.body.position[2] += finalDisp[2]

    // Wall slide: check for collisions and push out
    // Simple depenetration — real implementation would do iterative sweeps
    for (let attempt = 0; attempt < 3; attempt++) {
      let pushed = false
      const wallHit = this.world.raycast(
        this.body.position,
        vec3.normalize(vec3.create(), finalDisp),
        this.body.shape.boundingRadius() + this.skinWidth
      )

      if (wallHit && wallHit.body !== this.body && wallHit.body.type === 'static') {
        // Push out along hit normal
        const pushDist = this.body.shape.boundingRadius() + this.skinWidth - wallHit.distance
        if (pushDist > 0) {
          this.body.position[0] += wallHit.normal[0] * pushDist
          this.body.position[1] += wallHit.normal[1] * pushDist
          this.body.position[2] += wallHit.normal[2] * pushDist
          pushed = true
        }
      }
      if (!pushed) break
    }
  }

  /** Apply gravity and update vertical velocity. */
  applyGravity(gravity: Vec3, dt: number): void {
    if (!this.isGrounded) {
      this.velocity[0] += gravity[0] * dt
      this.velocity[1] += gravity[1] * dt
      this.velocity[2] += gravity[2] * dt
    } else {
      // Kill vertical velocity when grounded
      if (this.velocity[1] < 0) this.velocity[1] = 0
    }
  }

  /** Jump — sets upward velocity if grounded. */
  jump(height: number): void {
    if (!this.isGrounded) return
    // v = sqrt(2 * g * h)
    this.velocity[1] = Math.sqrt(2 * 9.81 * height)
    this.isGrounded = false
  }

  destroy(): void {
    this.world.removeBody(this.body)
  }
}
