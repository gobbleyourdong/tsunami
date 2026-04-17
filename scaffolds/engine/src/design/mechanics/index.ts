// Mechanics registry — the compiler produces GameDefinition, which lists
// which mechanic ids apply per scene. At scene start, the harness looks
// each id up in this registry, matches it to a MechanicRuntime factory,
// and constructs a live instance bound to the scene.
//
// Each mechanic module (sibling files in this directory) exports:
//   - a `register(registry)` call in module scope that adds its factory,
//     OR
//   - a named `<Type>Runtime` class implementing MechanicRuntime.
//
// The registry pattern keeps per-mechanic files self-contained so Tsunami
// can generate them one by one without touching a central switch.

import type { Game } from '../../game/game'
import type { MechanicInstance, MechanicType } from '../schema'

export interface MechanicRuntime {
  /** Called once when the scene containing this mechanic becomes active. */
  init(game: Game): void
  /** Called every frame while the mechanic's scene is active. */
  update(dt: number): void
  /** Called when the scene deactivates (pause, transition, game over). */
  dispose(): void
  /** Named output values this mechanic publishes for HUD / other mechanics. */
  expose?(): Record<string, unknown>
}

export type MechanicFactory = (instance: MechanicInstance, game: Game) => MechanicRuntime

class MechanicRegistry {
  private factories = new Map<MechanicType, MechanicFactory>()

  register(type: MechanicType, factory: MechanicFactory): void {
    if (this.factories.has(type)) {
      // Non-fatal — silently overwrite so hot-reload in dev loops doesn't
      // throw on repeat registration. Production builds should only
      // register each mechanic once.
      console.warn(`[mechanics] re-registering ${type}`)
    }
    this.factories.set(type, factory)
  }

  has(type: MechanicType): boolean {
    return this.factories.has(type)
  }

  create(instance: MechanicInstance, game: Game): MechanicRuntime | null {
    const factory = this.factories.get(instance.type)
    if (!factory) {
      console.warn(`[mechanics] no runtime for ${instance.type}; skipping`)
      return null
    }
    return factory(instance, game)
  }

  registeredTypes(): MechanicType[] {
    return [...this.factories.keys()]
  }
}

export const mechanicRegistry = new MechanicRegistry()

// Phase 1 registrations — importing a mechanic file has the side effect
// of registering its factory. Add lines here as each Phase 1 mechanic
// lands. Phase 2+ mechanics auto-register via the same pattern.
import './rhythm_track'
import './dialog_tree'
import './procedural_room_chain'
import './bullet_pattern'
import './puzzle_object'
// Phase 2
import './embedded_minigame'
// world_flags is a helper module, not a mechanic — import its exports
// from mechanics/world_flags.ts directly when needed.
// Phase 3 — action-core (13 mechanics, batched across commits)
import './difficulty'
import './wave_spawner'
import './hud'
import './lose_on_zero'
import './win_on_count'
import './pickup_loop'
import './score_combos'
import './checkpoint_progression'
import './lock_and_key'
import './camera_follow'
