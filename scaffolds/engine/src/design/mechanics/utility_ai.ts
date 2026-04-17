// UtilityAI — Phase 4 extension mechanic.
//
// Need-driven AI: each need decays at decay_per_sec, actions reduce named
// needs by need_deltas. Selection pick strategy: highest_need (greedy), or
// weighted_sample / expected_utility (probabilistic). v1 ships greedy +
// weighted_sample; expected_utility falls back to greedy.
//
// Per-archetype-instance state — the mechanic tracks one NeedState per
// entity tagged with the archetype so e.g. multiple enemies each have
// their own hunger.

import type { Game } from '../../game/game'
import type { ActionRef, MechanicInstance, UtilityAIParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy } from './world_flags'

interface NeedState { [needName: string]: number }

class UtilityAIRuntime implements MechanicRuntime {
  private params: UtilityAIParams
  private game!: Game
  private needsByEntityId = new Map<string, NeedState>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as UtilityAIParams
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    const entities = this.findInstances()
    for (const e of entities) {
      const id = this.entityId(e)
      let state = this.needsByEntityId.get(id)
      if (!state) {
        state = this.seedNeeds()
        this.needsByEntityId.set(id, state)
      }
      // Decay.
      for (const n of this.params.needs ?? []) {
        state[n.name] = Math.max(0, Math.min(n.max, (state[n.name] ?? 0) + n.decay_per_sec * dt))
      }
      // Pick action.
      const action = this.pickAction(state)
      if (action) {
        this.applyDeltas(state, action.need_deltas)
        this.fire(action.effect)
      }
    }
  }

  dispose(): void { this.needsByEntityId.clear() }

  expose(): Record<string, unknown> {
    return {
      instances: this.needsByEntityId.size,
      actions: (this.params.actions ?? []).map(a => a.name),
    }
  }

  private seedNeeds(): NeedState {
    const out: NeedState = {}
    for (const n of this.params.needs ?? []) {
      out[n.name] = n.initial ?? 0
    }
    return out
  }

  private pickAction(state: NeedState): UtilityAIParams['actions'][number] | null {
    const eligible = (this.params.actions ?? []).filter(a => {
      if (!a.precondition) return true
      return flagTruthy(this.game, a.precondition)
    })
    if (eligible.length === 0) return null
    const scored = eligible.map(a => ({
      action: a,
      score: this.scoreAction(a.need_deltas, state),
    }))
    if (this.params.selection === 'weighted_sample') {
      const total = scored.reduce((s, x) => s + Math.max(0, x.score), 0)
      if (total <= 0) return scored[0].action
      let r = Math.random() * total
      for (const x of scored) {
        r -= Math.max(0, x.score)
        if (r <= 0) return x.action
      }
    }
    // highest_need / expected_utility fallback: pick max score.
    scored.sort((a, b) => b.score - a.score)
    return scored[0].action
  }

  private scoreAction(deltas: Record<string, number>, state: NeedState): number {
    // Score = sum of (need_value * -delta) — actions that reduce a high
    // need score highest.
    let s = 0
    for (const [k, d] of Object.entries(deltas)) {
      s += (state[k] ?? 0) * -d
    }
    return s
  }

  private applyDeltas(state: NeedState, deltas: Record<string, number>): void {
    for (const [k, d] of Object.entries(deltas)) {
      const needSpec = (this.params.needs ?? []).find(n => n.name === k)
      const max = needSpec?.max ?? 100
      state[k] = Math.max(0, Math.min(max, (state[k] ?? 0) + d))
    }
  }

  private findInstances(): Array<Record<string, unknown>> {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    return entities.filter(e => e.type === aid)
  }

  private entityId(e: Record<string, unknown>): string {
    return String(e.name ?? JSON.stringify(e.position))
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

mechanicRegistry.register('UtilityAI', (instance, game) => {
  const rt = new UtilityAIRuntime(instance)
  rt.init(game)
  return rt
})
