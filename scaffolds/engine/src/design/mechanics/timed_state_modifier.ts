// TimedStateModifier — Phase 3 action-core mechanic.
//
// Applies a named state to an archetype for duration_sec, fires on_apply
// at the start and on_expire at the end. stackable=true lets multiple
// instances of the same state run in parallel (invuln + powered_up both
// set). stackable=false refreshes the single timer to duration_sec.

import type { Game } from '../../game/game'
import type { ActionRef, MechanicInstance, TimedStateModifierParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

interface ActiveTimer {
  entity: Record<string, unknown>
  remainingSec: number
}

class TimedStateModifierRuntime implements MechanicRuntime {
  private params: TimedStateModifierParams
  private game!: Game
  private active: ActiveTimer[] = []

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as TimedStateModifierParams
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    for (let i = this.active.length - 1; i >= 0; i--) {
      const t = this.active[i]
      t.remainingSec -= dt
      if (t.remainingSec <= 0) {
        this.removeState(t.entity)
        if (this.params.on_expire) this.fire(this.params.on_expire)
        this.active.splice(i, 1)
      }
    }
  }

  dispose(): void {
    for (const t of this.active) this.removeState(t.entity)
    this.active = []
  }

  /** External call to apply the state. Caller passes the instance
   *  (an entity in the active scene). */
  apply(entity?: Record<string, unknown>): void {
    const e = entity ?? this.findFirstEntity()
    if (!e) return
    if (!this.params.stackable) {
      // Refresh existing timer for this entity.
      const existing = this.active.find(t => t.entity === e)
      if (existing) {
        existing.remainingSec = this.params.duration_sec
        return
      }
    }
    this.addState(e)
    this.active.push({ entity: e, remainingSec: this.params.duration_sec })
    if (this.params.on_apply) this.fire(this.params.on_apply)
  }

  expose(): Record<string, unknown> {
    return {
      activeCount: this.active.length,
      state: this.params.state,
      stackable: this.params.stackable ?? false,
    }
  }

  private addState(entity: Record<string, unknown>): void {
    const props = (entity.properties ?? {}) as Record<string, unknown>
    const states = ((props.states ?? []) as string[]).slice()
    if (!states.includes(this.params.state)) states.push(this.params.state)
    props.states = states
    entity.properties = props
  }

  private removeState(entity: Record<string, unknown>): void {
    const props = (entity.properties ?? {}) as Record<string, unknown>
    const states = ((props.states ?? []) as string[]).filter(s => s !== this.params.state)
    props.states = states
    entity.properties = props
  }

  private findFirstEntity(): Record<string, unknown> | null {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    return entities.find(e => e.type === aid) ?? null
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

mechanicRegistry.register('TimedStateModifier', (instance, game) => {
  const rt = new TimedStateModifierRuntime(instance)
  rt.init(game)
  return rt
})
