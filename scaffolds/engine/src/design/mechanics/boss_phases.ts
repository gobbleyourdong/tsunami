// BossPhases — Phase 4 extension mechanic.
//
// Multi-phase boss AI. As the boss's Health drops below each phase's
// health_pct threshold, the mechanic swaps in the phase's AI name, applies
// tint override, and fires on_phase_enter ActionRefs. Phases are consumed
// once; reverting health doesn't re-trigger earlier phases.

import type { Game } from '../../game/game'
import type { ActionRef, BossPhasesParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class BossPhasesRuntime implements MechanicRuntime {
  private params: BossPhasesParams
  private game!: Game
  private currentPhaseIdx = -1

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as BossPhasesParams
  }

  init(game: Game): void {
    this.game = game
    // Phase 0 applied at the start.
    this.enterPhase(0)
  }

  update(_dt: number): void {
    const boss = this.findBoss()
    if (!boss) return
    const props = (boss.properties as Record<string, unknown> | undefined) ?? {}
    const health = (props.Health as number | undefined) ?? 100
    const maxHealth = 100  // v1 assumption; future: read from archetype defaults

    const pct = (health / maxHealth) * 100
    // Find the highest-index phase whose threshold we've passed.
    let nextIdx = this.currentPhaseIdx
    for (let i = this.currentPhaseIdx + 1; i < (this.params.phases?.length ?? 0); i++) {
      if (pct <= this.params.phases[i].health_pct) nextIdx = i
      else break
    }
    if (nextIdx > this.currentPhaseIdx) this.enterPhase(nextIdx)
  }

  dispose(): void { /* boss state persists on entity */ }

  expose(): Record<string, unknown> {
    return {
      currentPhaseIdx: this.currentPhaseIdx,
      totalPhases: this.params.phases?.length ?? 0,
    }
  }

  private enterPhase(idx: number): void {
    const phase = this.params.phases?.[idx]
    if (!phase) return
    this.currentPhaseIdx = idx
    const boss = this.findBoss()
    if (boss) {
      const props = (boss.properties ?? {}) as Record<string, unknown>
      props.ai = phase.ai
      if (phase.tint) props.tint = phase.tint
      boss.properties = props
    }
    for (const a of phase.on_phase_enter ?? []) this.fire(a)
  }

  private findBoss(): Record<string, unknown> | null {
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

mechanicRegistry.register('BossPhases', (instance, game) => {
  const rt = new BossPhasesRuntime(instance)
  rt.init(game)
  return rt
})
