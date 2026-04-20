/**
 * MainScene — the blank scene every custom scaffold starts from.
 *
 * GENRE SCAFFOLDS override this file entirely. For a fighting game:
 *   import { HealthBar, ComboAttacks, GameClock } from '@engine/mechanics'
 *   import characters from '../data/characters.json'
 *   import rules from '../data/rules.json'
 *
 *   export class Fight extends MainScene {
 *     setup() {
 *       characters.forEach(c => {
 *         new HealthBar({ target: c.id, anchor: c.team === 1 ? 'top-left' : 'top-right' })
 *         new ComboAttacks({ moveset: c.moveset })
 *       })
 *       new GameClock({ duration: rules.timer_sec })
 *     }
 *   }
 *
 * See @engine/mechanics for the full catalog (35 runtime mechanics registered).
 * See @engine/components for the component vocabulary (17 canonical types).
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { ComponentBag } from '@engine/components'

/** Entity shape compatible with @engine/game's EntityDef. Genre scaffolds
 *  can extend this with additional fields. */
export interface SceneEntity {
  id: string
  name?: string
  components?: ComponentBag
  properties?: Record<string, unknown>
}

export class MainScene {
  readonly name = 'custom-main'
  protected entities: SceneEntity[] = []
  protected mechanics: MechanicRuntime[] = []

  /** Called once at scene load. Override to compose mechanics + spawn entities. */
  setup(): void {
    // Default: empty scene. Override in genre-specific subclasses.
    // Example (commented):
    //
    // this.entities.push({
    //   id: 'player',
    //   components: {
    //     Health: { current: 100, max: 100 },
    //     Position: { x: 100, y: 100 },
    //     Tags: ['player'],
    //   },
    // })
    //
    // this.mountMechanic('HealthBar', { target: 'player', anchor: 'top-left' })
  }

  /** Helper: instantiate a registered mechanic by name + params.
   *  Returns null if the type isn't registered (logs a warning).
   *  Genre scaffolds use this to compose from the catalog. */
  protected mountMechanic(type: string, params: Record<string, unknown>): MechanicRuntime | null {
    const instance = {
      id: `${type}_${this.mechanics.length}`,
      type: type as any,
      params,
    }
    const rt = mechanicRegistry.create(instance as any, null as any)
    if (rt) this.mechanics.push(rt)
    return rt
  }

  /** Called when the scene deactivates. */
  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch (e) { console.error(`dispose failed: ${e}`) }
    }
    this.mechanics.length = 0
    this.entities.length = 0
  }
}
