/**
 * Pickup manager — health, speed boost, rapid fire, shield.
 */

import type { GameState } from './state'
import type { PlayerController } from './player'

export type PickupType = 'health' | 'speed' | 'rapidfire' | 'shield'

export interface Pickup {
  x: number
  y: number
  type: PickupType
  radius: number
  lifetime: number
  bobPhase: number
}

const PICKUP_COLORS: Record<PickupType, string> = {
  health: '#ff4444',
  speed: '#4488ff',
  rapidfire: '#ffcc00',
  shield: '#44ccff',
}

export class PickupManager {
  pickups: Pickup[] = []
  private state: GameState

  constructor(state: GameState) {
    this.state = state
  }

  spawn(x: number, y: number, type: PickupType): void {
    this.pickups.push({
      x, y, type,
      radius: 0.25,
      lifetime: 10,
      bobPhase: Math.random() * Math.PI * 2,
    })
  }

  spawnRandom(x: number, y: number): void {
    const types: PickupType[] = ['health', 'speed', 'rapidfire', 'shield']
    const weights = [0.4, 0.2, 0.2, 0.2]
    let r = Math.random()
    for (let i = 0; i < types.length; i++) {
      r -= weights[i]
      if (r <= 0) {
        this.spawn(x, y, types[i])
        return
      }
    }
    this.spawn(x, y, 'health')
  }

  update(dt: number, player: PlayerController): void {
    const toRemove: number[] = []

    for (let i = 0; i < this.pickups.length; i++) {
      const p = this.pickups[i]
      p.lifetime -= dt

      if (p.lifetime <= 0) {
        toRemove.push(i)
        continue
      }

      // Collision with player
      const dx = p.x - player.x
      const dy = p.y - player.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < p.radius + player.radius) {
        this.applyPickup(p.type, player)
        toRemove.push(i)
      }
    }

    for (let i = toRemove.length - 1; i >= 0; i--) {
      this.pickups.splice(toRemove[i], 1)
    }
  }

  private applyPickup(type: PickupType, player: PlayerController): void {
    switch (type) {
      case 'health':
        this.state.playerHealth.heal(25)
        break
      case 'speed':
        player.speedBoostTimer = 5
        break
      case 'rapidfire':
        player.rapidFireTimer = 5
        break
      case 'shield':
        player.shieldTimer = 5
        break
    }
    this.state.score.addPoints(5) // bonus for pickup
  }

  clear(): void {
    this.pickups.length = 0
  }
}

export { PICKUP_COLORS }
