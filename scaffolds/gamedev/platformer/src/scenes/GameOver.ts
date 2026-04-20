/**
 * GameOver scene — hit on lives=0. "Continue?" prompt; on Yes, reset
 * to last continue-checkpoint; on No, return to Title.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'

export class GameOver {
  readonly name = 'gameover'
  description = 'Game Over — continue?'
  private mechanics: MechanicRuntime[] = []

  setup(): void {
    this.tryMount('HUD', {
      fields: [
        { label: 'GAME OVER',     static: true },
        { label: 'CONTINUE? Y/N', static: true },
      ],
      layout: 'center',
    })
    this.tryMount('ChipMusic', {
      base_track: 'gameover_theme',
      bpm: 80,
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
