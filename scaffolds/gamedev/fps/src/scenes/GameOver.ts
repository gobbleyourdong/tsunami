/**
 * GameOver scene — hit on player Health=0. Continue prompt.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'

export class GameOver {
  readonly name = 'gameover'
  description = 'Game Over — restart mission'
  private mechanics: MechanicRuntime[] = []

  setup(): void {
    this.tryMount('HUD', {
      fields: [
        { label: 'YOU DIED',      static: true },
        { label: 'RESTART? Y/N',  static: true },
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
      config: { mode: '3d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
