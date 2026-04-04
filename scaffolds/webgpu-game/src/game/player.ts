/**
 * Player controller — WASD movement, mouse aim, shooting.
 */

import { KeyboardInput } from '@engine/input/keyboard'
import { ActionMap } from '@engine/input/action_map'
import type { GameState } from './state'
import type { ProjectileManager } from './projectiles'

export class PlayerController {
  x = 0
  y = 0  // top-down, y = z in world space
  radius = 0.4
  speed = 5
  aimAngle = 0
  shootCooldown = 0
  shootRate = 0.15  // seconds between shots

  // Knockback
  knockbackX = 0
  knockbackY = 0

  // Powerups
  speedBoostTimer = 0
  rapidFireTimer = 0
  shieldTimer = 0

  private state: GameState
  private keyboard: KeyboardInput
  private actions: ActionMap

  // Mouse tracking
  mouseX = 0
  mouseY = 0

  constructor(state: GameState, keyboard: KeyboardInput, actions: ActionMap) {
    this.state = state
    this.keyboard = keyboard
    this.actions = actions

    // Track mouse position
    window.addEventListener('mousemove', (e) => {
      this.mouseX = e.clientX
      this.mouseY = e.clientY
    })
  }

  update(dt: number, projectiles: ProjectileManager): void {
    if (this.state.playerHealth.isDead) return

    // Movement
    let dx = 0, dy = 0
    if (this.keyboard.isDown('KeyW') || this.keyboard.isDown('ArrowUp')) dy -= 1
    if (this.keyboard.isDown('KeyS') || this.keyboard.isDown('ArrowDown')) dy += 1
    if (this.keyboard.isDown('KeyA') || this.keyboard.isDown('ArrowLeft')) dx -= 1
    if (this.keyboard.isDown('KeyD') || this.keyboard.isDown('ArrowRight')) dx += 1

    // Normalize diagonal
    const len = Math.sqrt(dx * dx + dy * dy)
    if (len > 0) {
      dx /= len
      dy /= len
    }

    const currentSpeed = this.speed * (this.speedBoostTimer > 0 ? 2 : 1)
    this.x += dx * currentSpeed * dt
    this.y += dy * currentSpeed * dt

    // Apply knockback
    this.x += this.knockbackX * dt * 10
    this.y += this.knockbackY * dt * 10
    this.knockbackX *= 0.9
    this.knockbackY *= 0.9

    // Clamp to arena bounds
    const bound = 12
    this.x = Math.max(-bound, Math.min(bound, this.x))
    this.y = Math.max(-bound, Math.min(bound, this.y))

    // Aim toward mouse (approximate: center of screen = player position)
    const cx = window.innerWidth / 2
    const cy = window.innerHeight / 2
    this.aimAngle = Math.atan2(this.mouseY - cy, this.mouseX - cx)

    // Shooting
    this.shootCooldown -= dt
    const rate = this.rapidFireTimer > 0 ? this.shootRate / 3 : this.shootRate
    if (this.keyboard.isDown('Space') && this.shootCooldown <= 0) {
      this.shootCooldown = rate
      const speed = 15
      projectiles.spawn(
        this.x, this.y,
        Math.cos(this.aimAngle) * speed,
        Math.sin(this.aimAngle) * speed,
        'player', 10
      )
    }

    // Powerup timers
    this.speedBoostTimer = Math.max(0, this.speedBoostTimer - dt)
    this.rapidFireTimer = Math.max(0, this.rapidFireTimer - dt)
    this.shieldTimer = Math.max(0, this.shieldTimer - dt)
  }

  takeDamage(amount: number, fromX: number, fromY: number): void {
    if (this.shieldTimer > 0) {
      this.shieldTimer = Math.max(0, this.shieldTimer - 0.5)
      return
    }
    this.state.playerHealth.takeDamage({ amount, type: 'physical' })

    // Knockback away from source
    const dx = this.x - fromX
    const dy = this.y - fromY
    const d = Math.sqrt(dx * dx + dy * dy) || 1
    this.knockbackX = (dx / d) * 3
    this.knockbackY = (dy / d) * 3
  }
}
