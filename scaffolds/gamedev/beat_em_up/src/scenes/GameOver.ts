/**
 * GameOver scene — all brawlers KO'd with no continues left.
 *
 * Arcade convention: continue-countdown timer (10s) — if player
 * inserts coin (presses Start) the run continues; else returns to Title.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'

export class GameOver {
  readonly name = 'gameover'
  description = 'GAME OVER — continue? (arcade 10s)'
  private mechanics: MechanicRuntime[] = []

  setup(): void {
    this.tryMount('HUD', {
      fields: [
        { label: 'GAME OVER',      static: true },
        { label: 'CONTINUE? 10',   static: true },
      ],
      layout: 'center',
    })
    this.tryMount('ChipMusic', {
      base_track: 'gameover_theme',
      bpm: 70,
      loop: false,
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
  }

  private tryMount(type: string, params: Record<string, unknown>): void {
    const instance = {
      id: `${type}_${this.mechanics.length}`, type, params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, this.makeStubGame())
    if (rt) this.mechanics.push(rt)
  }

  private makeStubGame(): any {
    return {
      sceneManager: { activeScene: () => ({ entities: [] }) },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
