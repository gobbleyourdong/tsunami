// EndingBranches — Phase 4 extension mechanic.
//
// Multi-ending selection. Each ending has a list of requirements (world
// flags, conditions, archetype counts, elapsed-time bounds). On game-end
// (a terminal condition fires elsewhere), the mechanic walks endings in
// priority order and returns the first one whose requirements are all
// satisfied. default_ending is the fallback when nothing matches.

import type { Game } from '../../game/game'
import type { EndingBranchesParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy, readWorldFlag } from './world_flags'

type Ending = EndingBranchesParams['endings'][number]

class EndingBranchesRuntime implements MechanicRuntime {
  private params: EndingBranchesParams
  private game!: Game
  private startedAtSec: number
  private elapsedSec = 0
  private selected: string | null = null

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as EndingBranchesParams
    this.startedAtSec = performance.now() / 1000
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void { this.elapsedSec += dt }

  dispose(): void { /* result persists for flow to query */ }

  /** External: game flow calls this at terminal state to pick an ending. */
  selectEnding(): { id: string; scene: string } {
    const sorted = (this.params.endings ?? []).slice().sort(
      (a, b) => (b.priority ?? 0) - (a.priority ?? 0)
    )
    for (const e of sorted) {
      if (this.requirementsMet(e)) {
        this.selected = e.id
        return { id: e.id, scene: e.scene as unknown as string }
      }
    }
    // Fallback.
    const def = (this.params.endings ?? []).find(e => e.id === this.params.default_ending)
    this.selected = def?.id ?? this.params.default_ending
    return {
      id: this.selected as string,
      scene: (def?.scene as unknown as string) ?? (this.selected as string),
    }
  }

  expose(): Record<string, unknown> {
    return {
      selected: this.selected,
      elapsedSec: this.elapsedSec,
      endings: (this.params.endings ?? []).map(e => ({ id: e.id, priority: e.priority ?? 0 })),
    }
  }

  private requirementsMet(e: Ending): boolean {
    for (const r of e.requires ?? []) {
      const rw = r as Record<string, unknown>
      if ('world_flag' in rw) {
        const v = readWorldFlag(this.game, rw.world_flag as string)
        if ('value' in rw) { if (v !== rw.value) return false }
        else if (v === undefined || v === false) return false
        continue
      }
      if ('condition' in rw) {
        if (!flagTruthy(this.game, rw.condition as string)) return false
        continue
      }
      if ('archetype_count' in rw) {
        const ac = rw.archetype_count as { archetype: string; min?: number; max?: number }
        const n = this.countArchetype(ac.archetype)
        if (typeof ac.min === 'number' && n < ac.min) return false
        if (typeof ac.max === 'number' && n > ac.max) return false
        continue
      }
      if ('elapsed_sec' in rw) {
        const es = rw.elapsed_sec as { max?: number }
        if (typeof es.max === 'number' && this.elapsedSec > es.max) return false
      }
    }
    return true
  }

  private countArchetype(aid: string): number {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    return entities.reduce((n, e) => n + (e.type === aid ? 1 : 0), 0)
  }
}

mechanicRegistry.register('EndingBranches', (instance, game) => {
  const rt = new EndingBranchesRuntime(instance)
  rt.init(game)
  return rt
})
