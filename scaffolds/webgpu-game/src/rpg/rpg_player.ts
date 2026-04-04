/**
 * RPG Player — grid-based movement, interaction, combat stats.
 */

import { KeyboardInput } from '@engine/input/keyboard'
import { HealthSystem } from '@engine/systems/health'
import { Inventory, ItemDef } from '@engine/systems/inventory'
import { WorldMap, canMoveTo, NPCDef } from './world'

export class RPGPlayer {
  x: number  // tile position (float for smooth movement)
  y: number
  targetX: number  // tile we're moving toward
  targetY: number
  facing: 'up' | 'down' | 'left' | 'right' = 'down'
  moving = false
  moveSpeed = 4  // tiles per second

  health: HealthSystem
  inventory: Inventory
  sprite = 'player_warrior'

  // Combat
  attackPower = 10
  attackCooldown = 0
  attackRange = 1.5  // tiles

  // Interaction
  interactTarget: NPCDef | null = null

  private keyboard: KeyboardInput
  private moveTimer = 0
  private inputBuffer: 'up' | 'down' | 'left' | 'right' | null = null

  constructor(keyboard: KeyboardInput, startX: number, startY: number) {
    this.keyboard = keyboard
    this.x = startX
    this.y = startY
    this.targetX = startX
    this.targetY = startY
    this.health = new HealthSystem(100)
    this.inventory = new Inventory(12)
  }

  update(dt: number, map: WorldMap): void {
    this.attackCooldown = Math.max(0, this.attackCooldown - dt)

    // Read input direction
    let dx = 0, dy = 0
    if (this.keyboard.isDown('KeyW') || this.keyboard.isDown('ArrowUp')) { dy = -1; this.inputBuffer = 'up' }
    else if (this.keyboard.isDown('KeyS') || this.keyboard.isDown('ArrowDown')) { dy = 1; this.inputBuffer = 'down' }
    else if (this.keyboard.isDown('KeyA') || this.keyboard.isDown('ArrowLeft')) { dx = -1; this.inputBuffer = 'left' }
    else if (this.keyboard.isDown('KeyD') || this.keyboard.isDown('ArrowRight')) { dx = 1; this.inputBuffer = 'right' }
    else { this.inputBuffer = null }

    if (!this.moving && this.inputBuffer) {
      // Start new movement
      this.facing = this.inputBuffer
      const nx = Math.round(this.x) + dx
      const ny = Math.round(this.y) + dy
      if (canMoveTo(map, nx, ny)) {
        this.targetX = nx
        this.targetY = ny
        this.moving = true
      }
    }

    // Smooth movement toward target
    if (this.moving) {
      const speed = this.moveSpeed * dt
      const dx2 = this.targetX - this.x
      const dy2 = this.targetY - this.y
      const dist = Math.sqrt(dx2 * dx2 + dy2 * dy2)

      if (dist <= speed) {
        this.x = this.targetX
        this.y = this.targetY
        this.moving = false
      } else {
        this.x += (dx2 / dist) * speed
        this.y += (dy2 / dist) * speed
      }
    }

    // Check for map exits
    for (const exit of map.exits) {
      if (Math.round(this.x) === exit.x && Math.round(this.y) === exit.y) {
        // Signal map transition (handled by RPG main loop)
        this.interactTarget = { id: '__exit__', name: exit.target, sprite: '', x: exit.spawnX, y: exit.spawnY, dialog: [] }
      }
    }
  }

  /** Get the tile position the player is facing. */
  getFacingTile(): [number, number] {
    const px = Math.round(this.x)
    const py = Math.round(this.y)
    switch (this.facing) {
      case 'up': return [px, py - 1]
      case 'down': return [px, py + 1]
      case 'left': return [px - 1, py]
      case 'right': return [px + 1, py]
    }
  }

  /** Find the nearest NPC in facing direction within range. */
  findNearbyNPC(map: WorldMap): NPCDef | null {
    const [fx, fy] = this.getFacingTile()
    for (const npc of map.npcs) {
      const dist = Math.sqrt((npc.x - fx) ** 2 + (npc.y - fy) ** 2)
      if (dist < this.attackRange) return npc
    }
    return null
  }

  /** Check if player can attack (cooldown ready). */
  canAttack(): boolean {
    return this.attackCooldown <= 0
  }

  /** Perform attack, return damage dealt. */
  attack(): number {
    if (!this.canAttack()) return 0
    this.attackCooldown = 0.5
    return this.attackPower
  }
}
