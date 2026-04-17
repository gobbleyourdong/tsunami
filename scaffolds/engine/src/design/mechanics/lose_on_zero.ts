// LoseOnZero — Phase 3 action-core mechanic.
//
// Watches a named field on one archetype (or any_of a set) and emits
// emit_condition as a world_flag=true when the field reaches 0 or below.
// Party-wipe case: any_of requires ALL archetypes in the list to hit 0.

import type { Game } from '../../game/game'
import type { LoseOnZeroParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag, flagTruthy } from './world_flags'

class LoseOnZeroRuntime implements MechanicRuntime {
  private params: LoseOnZeroParams
  private game!: Game
  private fired = false

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as LoseOnZeroParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    if (this.fired) return
    // Already emitted earlier? (scene reset can resurrect this mechanic
    // but the flag may still hold from the prior run.)
    if (flagTruthy(this.game, this.params.emit_condition as unknown as string)) {
      this.fired = true
      return
    }
    if (this.conditionMet()) {
      writeWorldFlag(this.game, this.params.emit_condition as unknown as string, true)
      this.fired = true
    }
  }

  dispose(): void { /* nothing to clean up */ }

  expose(): Record<string, unknown> {
    return { fired: this.fired }
  }

  private conditionMet(): boolean {
    const archs = this.archetypeIds()
    if (archs.length === 0) return false
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    for (const aid of archs) {
      const matching = entities.filter(e => e.type === aid)
      if (matching.length === 0) {
        // No instances currently — treat as not-yet-lost for THIS archetype.
        return false
      }
      const anyAlive = matching.some(e => {
        const p = (e.properties as Record<string, unknown> | undefined) ?? {}
        const v = p[this.params.field] as number | undefined
        return typeof v === 'number' && v > 0
      })
      if (anyAlive) return false   // at least one is still above zero
    }
    return true
  }

  private archetypeIds(): string[] {
    const a = this.params.archetype as unknown
    if (typeof a === 'string') return [a]
    if (a && typeof a === 'object' && Array.isArray((a as Record<string, unknown>).any_of)) {
      return (a as Record<string, unknown>).any_of as string[]
    }
    return []
  }
}

mechanicRegistry.register('LoseOnZero', (instance, game) => {
  const rt = new LoseOnZeroRuntime(instance)
  rt.init(game)
  return rt
})
