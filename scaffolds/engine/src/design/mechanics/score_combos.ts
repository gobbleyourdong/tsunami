// ScoreCombos — Phase 3 action-core mechanic.
//
// Multiplies score awards during a rolling window. commit='window'
// commits on timeout; commit='event' banks multiplier on a named
// commit_event (THPS-style land-your-line pattern).
//
// v1 integrates via notifyScoreEvent(amount) calls from action
// dispatchers. The mechanic multiplies the incoming amount by the
// current multiplier and writes back to the archetype's Score
// component.

import type { Game } from '../../game/game'
import type { MechanicInstance, ScoreCombosParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class ScoreCombosRuntime implements MechanicRuntime {
  private params: ScoreCombosParams
  private game!: Game
  private windowEndsAtSec = 0
  private elapsedSec = 0
  private pendingPoints = 0
  private chainLen = 0
  private lastMultiplier = 1
  private totalBanked = 0

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as ScoreCombosParams
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    this.elapsedSec += dt
    if (this.params.commit === 'window' || this.params.commit === undefined) {
      if (this.chainLen > 0 && this.elapsedSec >= this.windowEndsAtSec) {
        this.commitPending()
      }
    }
  }

  dispose(): void { this.pendingPoints = 0; this.chainLen = 0 }

  /** External call from an award-score action. Returns the multiplied amount. */
  notifyScoreEvent(amount: number): number {
    this.chainLen += 1
    this.windowEndsAtSec = this.elapsedSec + this.params.window_sec
    const mul = this.currentMultiplier()
    this.lastMultiplier = mul
    const awarded = amount * mul
    this.pendingPoints += awarded
    if (this.params.commit === 'event') {
      // In event-commit mode nothing banks until the event fires.
      // The caller still gets the multiplied amount for immediate UI.
    }
    return awarded
  }

  /** External call when commit_event fires — only meaningful when commit='event'. */
  notifyCommitEvent(): void {
    if (this.params.commit === 'event') this.commitPending()
  }

  expose(): Record<string, unknown> {
    return {
      chainLen: this.chainLen,
      multiplier: this.lastMultiplier,
      pendingPoints: this.pendingPoints,
      totalBanked: this.totalBanked,
      secRemaining: Math.max(0, this.windowEndsAtSec - this.elapsedSec),
    }
  }

  private currentMultiplier(): number {
    const n = this.chainLen
    const cap = this.params.max_multiplier ?? 8
    let m = 1
    switch (this.params.curve) {
      case 'linear':      m = 1 + (n - 1) * 0.5; break
      case 'quadratic':   m = 1 + 0.1 * (n - 1) * (n - 1); break
      case 'exponential': m = Math.pow(1.3, Math.max(0, n - 1)); break
    }
    return Math.min(cap, Math.max(1, m))
  }

  private commitPending(): void {
    if (this.pendingPoints <= 0) return
    this.totalBanked += this.pendingPoints
    this.writeToPlayerScore(this.pendingPoints)
    this.pendingPoints = 0
    this.chainLen = 0
  }

  private writeToPlayerScore(delta: number): void {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    for (const e of entities) {
      if (e.type !== aid) continue
      const p = (e.properties ?? {}) as Record<string, unknown>
      p.Score = ((p.Score as number | undefined) ?? 0) + delta
      e.properties = p
      return
    }
  }
}

mechanicRegistry.register('ScoreCombos', (instance, game) => {
  const rt = new ScoreCombosRuntime(instance)
  rt.init(game)
  return rt
})
