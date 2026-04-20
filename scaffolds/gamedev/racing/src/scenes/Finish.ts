/**
 * Finish scene — race complete. Shows position + lap times + retry.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'

export class Finish {
  readonly name = 'finish'
  description = 'Race complete — results'
  private mechanics: MechanicRuntime[] = []

  setup(): void {
    this.tryMount('HUD', {
      fields: [
        { label: 'FINISH',            static: true },
        { singleton: 'final_position', label: 'POS' },
        { singleton: 'best_lap',       label: 'BEST' },
        { label: 'RESTART? Y/N',      static: true },
      ],
      layout: 'center',
    })
    this.tryMount('ChipMusic', {
      base_track: 'victory_theme',
      bpm: 120,
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
