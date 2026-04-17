// PickupLoop — Phase 3 action-core mechanic.
//
// Maintains a population of pickup archetype instances on the map,
// respawning them after sec or never. max_simultaneous caps active
// count. Reward is applied by the archetype's on_contact trigger on
// the player; this mechanic just keeps the supply stocked.

import type { Game } from '../../game/game'
import type { MechanicInstance, PickupLoopParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class PickupLoopRuntime implements MechanicRuntime {
  private params: PickupLoopParams
  private game!: Game
  private respawnQueue: number[] = []   // elapsedSec values when each respawn fires
  private elapsedSec = 0

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as PickupLoopParams
  }

  init(game: Game): void {
    this.game = game
    // Seed the map with one initial pickup.
    this.spawnOne()
  }

  update(dt: number): void {
    this.elapsedSec += dt
    // Drain fired respawns.
    while (this.respawnQueue.length > 0 && this.respawnQueue[0] <= this.elapsedSec) {
      this.respawnQueue.shift()
      if (this.atCap()) continue
      this.spawnOne()
    }
    // Count current live pickups; if someone collected one, enqueue respawn.
    const live = this.liveCount()
    const cap = this.params.max_simultaneous ?? 1
    const expected = Math.min(cap, 1 + this.respawnQueue.length)
    if (live < expected && this.params.respawn !== 'never') {
      this.respawnQueue.push(this.elapsedSec + this.params.respawn.sec)
    }
  }

  dispose(): void { this.respawnQueue = [] }

  expose(): Record<string, unknown> {
    return {
      liveCount: this.liveCount(),
      pendingRespawns: this.respawnQueue.length,
      cap: this.params.max_simultaneous ?? 1,
    }
  }

  private spawnOne(): void {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    if (!active) return
    const spawn = (active as Record<string, (type: string, opts?: Record<string, unknown>) => void>)
      .spawn
    if (typeof spawn !== 'function') return
    // Pickups land at random arena positions. v1 hard-codes a radius
    // matching common arenas; future pass wires arena bounds in.
    const r = 8
    const theta = Math.random() * Math.PI * 2
    const position: [number, number, number] = [Math.cos(theta) * r, 0, Math.sin(theta) * r]
    try { spawn(this.params.archetype as unknown as string, { position }) }
    catch { /* scene transitioning; drop it */ }
  }

  private liveCount(): number {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    return entities.reduce((n, e) => n + (e.type === aid ? 1 : 0), 0)
  }

  private atCap(): boolean {
    return this.liveCount() >= (this.params.max_simultaneous ?? 1)
  }
}

mechanicRegistry.register('PickupLoop', (instance, game) => {
  const rt = new PickupLoopRuntime(instance)
  rt.init(game)
  return rt
})
