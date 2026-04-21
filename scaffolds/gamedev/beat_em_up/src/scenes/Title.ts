/**
 * Title scene — press-start + character-select splash.
 *
 * Mounts ChipMusic (title theme) + HUD (press-start + char-select).
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import config from '../../data/config.json'

export class Title {
  readonly name = 'title'
  description = ''
  private mechanics: MechanicRuntime[] = []

  constructor() {
    const title = (config as any).meta?.title ?? 'Beat-em-up Scaffold'
    this.description = `${title} — press Start · select character`
  }

  setup(): void {
    this.tryMount('ChipMusic', {
      base_track: 'title_theme',
      bpm: 135,
      loop: true,
    })
    this.tryMount('HUD', {
      fields: [
        { label: 'PRESS START', static: true },
        { label: 'SELECT CHARACTER', static: true },
      ],
      layout: 'center',
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
