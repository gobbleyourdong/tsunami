/**
 * Enemy manager — 3 enemy types with behavior trees.
 * Rusher: charge player. Shooter: keep distance + fire. Tank: slow + tough.
 */

import { Sequence, Selector, Action, Condition, Wait } from '@engine/ai/behavior_tree'
import type { BTNode, BTStatus } from '@engine/ai/behavior_tree'
import type { GameState } from './state'
import type { PlayerController } from './player'
import type { ProjectileManager } from './projectiles'

export type EnemyType = 'rusher' | 'shooter' | 'tank'

export interface Enemy {
  id: number
  type: EnemyType
  x: number
  y: number
  radius: number
  health: number
  maxHealth: number
  speed: number
  damage: number
  shootCooldown: number
  dead: boolean
  deathTimer: number  // explosion animation timer
  tree: BTNode
  // State for AI
  targetX: number
  targetY: number
}

let enemyIdCounter = 0

const ENEMY_DEFS: Record<EnemyType, { health: number; speed: number; damage: number; radius: number }> = {
  rusher:  { health: 30, speed: 4.5, damage: 15, radius: 0.35 },
  shooter: { health: 40, speed: 2.5, damage: 10, radius: 0.4 },
  tank:    { health: 120, speed: 1.5, damage: 25, radius: 0.6 },
}

export class EnemyManager {
  enemies: Enemy[] = []
  private state: GameState

  constructor(state: GameState) {
    this.state = state
  }

  spawn(type: EnemyType, x: number, y: number): Enemy {
    const def = ENEMY_DEFS[type]
    const diff = this.state.difficulty

    const enemy: Enemy = {
      id: enemyIdCounter++,
      type,
      x, y,
      radius: def.radius,
      health: def.health * diff.get('enemyHealthMul'),
      maxHealth: def.health * diff.get('enemyHealthMul'),
      speed: def.speed * diff.get('enemySpeedMul'),
      damage: def.damage * diff.get('enemyDamageMul'),
      shootCooldown: 0,
      dead: false,
      deathTimer: 0,
      tree: this.createBehaviorTree(type),
      targetX: 0,
      targetY: 0,
    }

    this.enemies.push(enemy)
    return enemy
  }

  update(dt: number, player: PlayerController, projectiles: ProjectileManager): void {
    for (const enemy of this.enemies) {
      if (enemy.dead) {
        enemy.deathTimer -= dt
        continue
      }

      enemy.targetX = player.x
      enemy.targetY = player.y

      // Tick behavior tree
      enemy.tree.tick(dt)

      // Move toward target based on AI decision
      this.moveEnemy(enemy, dt, player)

      // Shooting (shooter type)
      if (enemy.type === 'shooter') {
        enemy.shootCooldown -= dt
        const dist = this.distToPlayer(enemy, player)
        if (dist < 8 && dist > 2 && enemy.shootCooldown <= 0) {
          enemy.shootCooldown = 1.5 / this.state.difficulty.get('spawnRateMul')
          const dx = player.x - enemy.x
          const dy = player.y - enemy.y
          const d = Math.sqrt(dx * dx + dy * dy) || 1
          projectiles.spawn(enemy.x, enemy.y, (dx / d) * 8, (dy / d) * 8, 'enemy', enemy.damage)
        }
      }

      // Melee collision with player
      const dist = this.distToPlayer(enemy, player)
      if (dist < enemy.radius + player.radius) {
        player.takeDamage(enemy.damage * dt * 2, enemy.x, enemy.y)
      }

      // Arena bounds
      const bound = 12.5
      enemy.x = Math.max(-bound, Math.min(bound, enemy.x))
      enemy.y = Math.max(-bound, Math.min(bound, enemy.y))
    }

    // Remove fully dead enemies (after death animation)
    this.enemies = this.enemies.filter(e => !e.dead || e.deathTimer > 0)
  }

  damageEnemy(enemy: Enemy, amount: number): boolean {
    enemy.health -= amount
    if (enemy.health <= 0 && !enemy.dead) {
      enemy.dead = true
      enemy.deathTimer = 0.3  // death animation duration
      this.state.score.addPoints(enemy.type === 'tank' ? 50 : enemy.type === 'shooter' ? 30 : 20)
      return true // killed
    }
    return false
  }

  get aliveCount(): number {
    return this.enemies.filter(e => !e.dead).length
  }

  clear(): void {
    this.enemies.length = 0
  }

  private moveEnemy(enemy: Enemy, dt: number, player: PlayerController): void {
    const dx = enemy.targetX - enemy.x
    const dy = enemy.targetY - enemy.y
    const dist = Math.sqrt(dx * dx + dy * dy) || 1

    let desiredDist = 0
    if (enemy.type === 'shooter') desiredDist = 5  // keep distance
    if (enemy.type === 'tank') desiredDist = 0.5

    if (dist > desiredDist + 0.5) {
      enemy.x += (dx / dist) * enemy.speed * dt
      enemy.y += (dy / dist) * enemy.speed * dt
    } else if (enemy.type === 'shooter' && dist < desiredDist - 0.5) {
      // Back away
      enemy.x -= (dx / dist) * enemy.speed * 0.5 * dt
      enemy.y -= (dy / dist) * enemy.speed * 0.5 * dt
    }

    // Separation from other enemies
    for (const other of this.enemies) {
      if (other === enemy || other.dead) continue
      const ox = enemy.x - other.x
      const oy = enemy.y - other.y
      const od = Math.sqrt(ox * ox + oy * oy)
      const minDist = enemy.radius + other.radius + 0.2
      if (od < minDist && od > 0.01) {
        const push = (minDist - od) * 0.5
        enemy.x += (ox / od) * push
        enemy.y += (oy / od) * push
      }
    }
  }

  private distToPlayer(enemy: Enemy, player: PlayerController): number {
    const dx = player.x - enemy.x
    const dy = player.y - enemy.y
    return Math.sqrt(dx * dx + dy * dy)
  }

  private createBehaviorTree(type: EnemyType): BTNode {
    // Simple trees — full BT nodes from the engine
    return new Action(() => 'success')  // Movement handled directly in update
  }
}
