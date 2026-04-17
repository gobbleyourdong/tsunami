// ComboAttacks — Phase 4 extension mechanic.
//
// Monitors an input-event stream and fires action when sequence of named
// button events occurs within window_ms. gated_by optionally requires
// a world_flag to be truthy (THPS "air-only" combos). External input
// bindings call notifyInput(eventName) on their keypress handler.

import type { Game } from '../../game/game'
import type { ActionRef, ComboAttacksParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy } from './world_flags'

type Pattern = ComboAttacksParams['patterns'][number]

interface InputEvent {
  name: string
  atMs: number
}

class ComboAttacksRuntime implements MechanicRuntime {
  private params: ComboAttacksParams
  private game!: Game
  private buffer: InputEvent[] = []
  private firedPatterns = 0

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as ComboAttacksParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    // Expire buffer entries older than the largest pattern window so
    // memory stays bounded.
    const now = performance.now()
    const maxWin = Math.max(500, ...(this.params.patterns ?? []).map(p => p.window_ms))
    while (this.buffer.length && (now - this.buffer[0].atMs) > maxWin) {
      this.buffer.shift()
    }
  }

  dispose(): void { this.buffer.length = 0 }

  /** External: input system calls this on each recognised button/event. */
  notifyInput(eventName: string): void {
    this.buffer.push({ name: eventName, atMs: performance.now() })
    this.checkPatterns()
  }

  expose(): Record<string, unknown> {
    return {
      firedPatterns: this.firedPatterns,
      bufferSize: this.buffer.length,
      patternNames: (this.params.patterns ?? []).map(p => p.name),
    }
  }

  private checkPatterns(): void {
    for (const p of this.params.patterns ?? []) {
      if (!this.sequenceMatches(p)) continue
      if (p.gated_by && !flagTruthy(this.game, p.gated_by)) continue
      this.fire(p.action)
      this.firedPatterns += 1
      // Consume matched events so the same sequence doesn't re-trigger
      // across partial overlaps.
      this.buffer.length = 0
      return
    }
  }

  private sequenceMatches(p: Pattern): boolean {
    if (this.buffer.length < p.sequence.length) return false
    const tail = this.buffer.slice(-p.sequence.length)
    const now = performance.now()
    if (now - tail[0].atMs > p.window_ms) return false
    for (let i = 0; i < p.sequence.length; i++) {
      if (tail[i].name !== p.sequence[i]) return false
    }
    return true
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

mechanicRegistry.register('ComboAttacks', (instance, game) => {
  const rt = new ComboAttacksRuntime(instance)
  rt.init(game)
  return rt
})
