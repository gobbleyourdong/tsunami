/**
 * RPG Combat — turn-free real-time combat with enemy HP, damage, loot.
 */

import { HealthSystem } from '@engine/systems/health'
import type { NPCDef, WorldMap } from './world'
import type { RPGPlayer } from './rpg_player'

export interface EnemyState {
  npcId: string
  health: HealthSystem
  hitFlash: number      // visual flash timer
  knockbackX: number
  knockbackY: number
  attackCooldown: number
  dead: boolean
  deathTimer: number
  loot: LootDrop[]
}

export interface LootDrop {
  itemId: string
  name: string
  chance: number  // 0-1
}

const ENEMY_STATS: Record<string, { hp: number; damage: number; speed: number; attackRate: number; loot: LootDrop[] }> = {
  rpg_wolf: {
    hp: 30, damage: 8, speed: 2, attackRate: 1.0,
    loot: [
      { itemId: 'wolf_pelt', name: 'Wolf Pelt', chance: 0.6 },
      { itemId: 'health_herb', name: 'Health Herb', chance: 0.3 },
    ],
  },
  rpg_spider: {
    hp: 20, damage: 5, speed: 3, attackRate: 0.7,
    loot: [
      { itemId: 'spider_silk', name: 'Spider Silk', chance: 0.5 },
      { itemId: 'venom_sac', name: 'Venom Sac', chance: 0.2 },
    ],
  },
}

export class CombatSystem {
  enemies = new Map<string, EnemyState>()
  worldDrops: { x: number; y: number; itemId: string; name: string; timer: number }[] = []

  // Callbacks for renderer
  onHit?: (enemyId: string, damage: number) => void
  onKill?: (enemyId: string, x: number, y: number) => void
  onPlayerHit?: (damage: number) => void

  /** Initialize enemy states from map NPCs. */
  initFromMap(map: WorldMap): void {
    this.enemies.clear()
    for (const npc of map.npcs) {
      if (!npc.hostile) continue
      const stats = ENEMY_STATS[npc.sprite]
      if (!stats) continue
      this.enemies.set(npc.id, {
        npcId: npc.id,
        health: new HealthSystem(stats.hp),
        hitFlash: 0,
        knockbackX: 0, knockbackY: 0,
        attackCooldown: Math.random() * stats.attackRate,  // stagger initial attacks
        dead: false,
        deathTimer: 0,
        loot: stats.loot,
      })
    }
  }

  update(dt: number, map: WorldMap, player: RPGPlayer): void {
    for (const npc of map.npcs) {
      if (!npc.hostile) continue
      const state = this.enemies.get(npc.id)
      if (!state || state.dead) continue

      const stats = ENEMY_STATS[npc.sprite] ?? { damage: 5, speed: 2, attackRate: 1 }

      // Chase player
      const dx = player.x - npc.x
      const dy = player.y - npc.y
      const dist = Math.sqrt(dx * dx + dy * dy)

      if (dist > 1.2 && dist < 8) {
        const speed = stats.speed * dt
        npc.x += (dx / dist) * speed + state.knockbackX * dt
        npc.y += (dy / dist) * speed + state.knockbackY * dt
      }

      // Knockback decay
      state.knockbackX *= 0.9
      state.knockbackY *= 0.9
      state.hitFlash = Math.max(0, state.hitFlash - dt)

      // Attack player on contact
      if (dist < 1.2) {
        state.attackCooldown -= dt
        if (state.attackCooldown <= 0) {
          state.attackCooldown = stats.attackRate
          player.health.takeDamage({ amount: stats.damage, type: 'physical' })
          this.onPlayerHit?.(stats.damage)
        }
      }
    }

    // Dead enemy cleanup
    for (const [id, state] of this.enemies) {
      if (state.dead) {
        state.deathTimer -= dt
        if (state.deathTimer <= 0) {
          // Remove NPC from map
          const idx = map.npcs.findIndex(n => n.id === id)
          if (idx >= 0) map.npcs.splice(idx, 1)
          this.enemies.delete(id)
        }
      }
    }

    // World drop timers
    this.worldDrops = this.worldDrops.filter(d => {
      d.timer -= dt
      // Player pickup
      const dx = player.x - d.x
      const dy = player.y - d.y
      if (Math.sqrt(dx * dx + dy * dy) < 1) {
        player.inventory.add({
          id: d.itemId, name: d.name, maxStack: 10, category: 'material',
        })
        return false
      }
      return d.timer > 0
    })
  }

  /** Player attacks — damage enemy in facing direction. */
  playerAttack(player: RPGPlayer, map: WorldMap): boolean {
    if (!player.canAttack()) return false
    const damage = player.attack()
    const [fx, fy] = player.getFacingTile()

    for (const npc of map.npcs) {
      if (!npc.hostile) continue
      const state = this.enemies.get(npc.id)
      if (!state || state.dead) continue

      const dist = Math.sqrt((npc.x - fx) ** 2 + (npc.y - fy) ** 2)
      if (dist < player.attackRange) {
        const actualDmg = state.health.takeDamage({ amount: damage, type: 'physical' })
        state.hitFlash = 0.15

        // Knockback away from player
        const dx = npc.x - player.x
        const dy = npc.y - player.y
        const d = Math.sqrt(dx * dx + dy * dy) || 1
        state.knockbackX = (dx / d) * 8
        state.knockbackY = (dy / d) * 8

        this.onHit?.(npc.id, actualDmg)

        if (state.health.isDead) {
          state.dead = true
          state.deathTimer = 0.5
          this.onKill?.(npc.id, npc.x, npc.y)

          // Drop loot
          for (const loot of state.loot) {
            if (Math.random() < loot.chance) {
              this.worldDrops.push({
                x: npc.x + (Math.random() - 0.5) * 0.5,
                y: npc.y + (Math.random() - 0.5) * 0.5,
                itemId: loot.itemId, name: loot.name,
                timer: 15,  // despawn after 15s
              })
            }
          }
        }
        return true
      }
    }
    return false
  }

  /** Get enemy state for rendering (hit flash, HP bar). */
  getEnemyState(npcId: string): EnemyState | undefined {
    return this.enemies.get(npcId)
  }
}
