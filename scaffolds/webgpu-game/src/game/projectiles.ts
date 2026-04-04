/**
 * Projectile manager — spawn, move, collide, despawn.
 */

import type { EnemyManager, Enemy } from './enemies'
import type { PlayerController } from './player'
import type { PickupManager } from './pickups'

export interface Projectile {
  x: number
  y: number
  vx: number
  vy: number
  owner: 'player' | 'enemy'
  damage: number
  lifetime: number
  radius: number
}

export class ProjectileManager {
  projectiles: Projectile[] = []
  onHit?: (x: number, y: number, killed: boolean) => void

  spawn(x: number, y: number, vx: number, vy: number, owner: 'player' | 'enemy', damage: number): void {
    this.projectiles.push({
      x, y, vx, vy, owner, damage,
      lifetime: 2,
      radius: owner === 'player' ? 0.12 : 0.1,
    })
  }

  update(
    dt: number,
    enemies: EnemyManager,
    player: PlayerController,
    pickups: PickupManager
  ): void {
    const bound = 13
    const toRemove = new Set<number>()

    for (let i = 0; i < this.projectiles.length; i++) {
      const p = this.projectiles[i]
      p.x += p.vx * dt
      p.y += p.vy * dt
      p.lifetime -= dt

      // Out of bounds or expired
      if (p.lifetime <= 0 || Math.abs(p.x) > bound || Math.abs(p.y) > bound) {
        toRemove.add(i)
        continue
      }

      // Player projectiles hit enemies
      if (p.owner === 'player') {
        for (const enemy of enemies.enemies) {
          if (enemy.dead) continue
          const dx = p.x - enemy.x
          const dy = p.y - enemy.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < p.radius + enemy.radius) {
            const killed = enemies.damageEnemy(enemy, p.damage)
            this.onHit?.(enemy.x, enemy.y, killed)
            if (killed) {
              if (Math.random() < 0.3) {
                pickups.spawnRandom(enemy.x, enemy.y)
              }
            }
            toRemove.add(i)
            break
          }
        }
      }

      // Enemy projectiles hit player
      if (p.owner === 'enemy') {
        const dx = p.x - player.x
        const dy = p.y - player.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < p.radius + player.radius) {
          player.takeDamage(p.damage, p.x, p.y)
          toRemove.add(i)
        }
      }
    }

    // Remove hit/expired projectiles (reverse order)
    const sorted = Array.from(toRemove).sort((a, b) => b - a)
    for (const idx of sorted) {
      this.projectiles.splice(idx, 1)
    }
  }

  clear(): void {
    this.projectiles.length = 0
  }
}
