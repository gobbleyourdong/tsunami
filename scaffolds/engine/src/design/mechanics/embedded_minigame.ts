// EmbeddedMinigame — Phase 2 composability mechanic.
//
// Nested design subtree. When the outer trigger condition fires, the
// runtime pauses a configured subset of the outer mechanics, spins up
// a small in-scene mechanic sandbox (the nested `mechanics` list), and
// runs them until exit_condition fires. On exit, outer mechanics resume
// and on_exit ActionRef fires.
//
// v1 scope: mechanics inside the minigame come from the SAME registry
// as the outer game — so any registered mechanic can be embedded. The
// inner mechanics share the active scene but use a suspended-set guard
// so HUD / WaveSpawner / etc. in the outer can pause cleanly.

import type { Game } from '../../game/game'
import type {
  ActionRef,
  EmbeddedMinigameParams,
  MechanicInstance,
} from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy } from './world_flags'

class EmbeddedMinigameRuntime implements MechanicRuntime {
  private params: EmbeddedMinigameParams
  private game!: Game
  private active = false
  private innerRuntimes: MechanicRuntime[] = []
  private suspendedIds = new Set<string>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as EmbeddedMinigameParams
    if (this.params.suspend_mechanics) {
      for (const id of this.params.suspend_mechanics) {
        this.suspendedIds.add(id as unknown as string)
      }
    }
  }

  init(game: Game): void {
    this.game = game
  }

  update(dt: number): void {
    if (!this.active) {
      if (this.checkTrigger()) this.enter()
      return
    }
    for (const rt of this.innerRuntimes) rt.update(dt)
    if (this.checkExit()) this.exit()
  }

  dispose(): void {
    for (const rt of this.innerRuntimes) rt.dispose()
    this.innerRuntimes.length = 0
    this.active = false
  }

  expose(): Record<string, unknown> {
    return {
      active: this.active,
      innerCount: this.innerRuntimes.length,
      suspendedOuter: [...this.suspendedIds],
    }
  }

  /** Test hook — returns the suspension set for the outer mechanic-tick
   *  loop. Outer loop should skip update() on any mechanic whose id is
   *  in this set while this minigame is active. */
  suspendedOuterIds(): string[] {
    return this.active ? [...this.suspendedIds] : []
  }

  // ───────── internals ─────────

  private enter(): void {
    this.active = true
    for (const mi of this.params.mechanics ?? []) {
      const rt = mechanicRegistry.create(mi, this.game)
      if (rt) this.innerRuntimes.push(rt)
    }
  }

  private exit(): void {
    for (const rt of this.innerRuntimes) rt.dispose()
    this.innerRuntimes.length = 0
    this.active = false
    if (this.params.on_exit) this.fire(this.params.on_exit)
  }

  private checkTrigger(): boolean {
    return this.resolveConditionKey(this.params.trigger as unknown as string)
  }

  private checkExit(): boolean {
    return this.resolveConditionKey(this.params.exit_condition as unknown as string)
  }

  private resolveConditionKey(key: string): boolean {
    if (!key) return false
    // Treat condition keys as world flags for the embedded gate. Real
    // condition emitters (LoseOnZero / WinOnCount) also write to
    // world_flags via the compiler, so a single probe covers both.
    return flagTruthy(this.game, key)
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

mechanicRegistry.register('EmbeddedMinigame', (instance, game) => {
  const rt = new EmbeddedMinigameRuntime(instance)
  rt.init(game)
  return rt
})
