// Mechanic registry — extracted from index.ts so individual mechanic
// modules can import {mechanicRegistry, MechanicRuntime} without
// creating the circular init hazard that index.ts' side-effect
// imports would otherwise introduce.
//
// Every mechanic file does:
//   import { mechanicRegistry, type MechanicRuntime } from './index'
// …which still works because index.ts re-exports from this file.
// But under the hood, this file is the source of truth — when a
// mechanic module side-effect-registers at load time, it imports
// _registry.ts directly (via index.ts), which is fully initialized
// regardless of the side-effect-import sequencing in index.ts.

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
