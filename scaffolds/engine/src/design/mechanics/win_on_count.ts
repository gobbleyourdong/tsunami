// WinOnCount — Phase 3 action-core mechanic.
//
// Counts live instances of an archetype and fires emit_condition once
// the count compares (eq / gte / lte) to the target. Common use:
// "N goals collected" or "boss count ≤ 0".

import type { Game } from '../../game/game'
import type { MechanicInstance, WinOnCountParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag, flagTruthy } from './world_flags'

class WinOnCountRuntime implements MechanicRuntime {
  private params: WinOnCountParams
  private game!: Game
  private fired = false
  private lastCount = 0

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as WinOnCountParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    if (this.fired) return
    if (flagTruthy(this.game, this.params.emit_condition as unknown as string)) {
      this.fired = true
      return
    }
    const count = this.countEntities()
    this.lastCount = count
    if (this.compare(count, this.params.count, this.params.comparison)) {
      writeWorldFlag(this.game, this.params.emit_condition as unknown as string, true)
      this.fired = true
    }
  }

  dispose(): void { /* nothing */ }

  expose(): Record<string, unknown> {
    return {
      count: this.lastCount,
      target: this.params.count,
      comparison: this.params.comparison,
      fired: this.fired,
    }
  }

  private countEntities(): number {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    return entities.reduce((n, e) => n + (e.type === aid ? 1 : 0), 0)
  }

  private compare(a: number, b: number, op: 'eq' | 'gte' | 'lte'): boolean {
    if (op === 'eq')  return a === b
    if (op === 'gte') return a >= b
    if (op === 'lte') return a <= b
    return false
  }
}

mechanicRegistry.register('WinOnCount', (instance, game) => {
  const rt = new WinOnCountRuntime(instance)
  rt.init(game)
  return rt
})
