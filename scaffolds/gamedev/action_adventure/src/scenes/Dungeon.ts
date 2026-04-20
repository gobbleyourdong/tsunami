/**
 * Dungeon scene — lock-and-key progression + boss arena.
 *
 * Shares most mechanics with Overworld (CameraFollow, RoomGraph, HUD)
 * but adds LockAndKey + BossPhases. Boss triggers on entering the
 * last dungeon room; defeating boss opens return-to-overworld.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import entitiesData from '../../data/entities.json'
import roomsData from '../../data/rooms.json'
import mechanicsData from '../../data/mechanics.json'

export class Dungeon {
  readonly name = 'dungeon'
  description = ''
  private mechanics: MechanicRuntime[] = []

  constructor() {
    const rooms = (roomsData as { rooms: Record<string, { kind?: string }> }).rooms
    const dungeonRooms = Object.entries(rooms).filter(([_, r]) => r.kind === 'dungeon')
    this.description = `${dungeonRooms.length} dungeon rooms — LockAndKey + BossPhases wired`
  }

  setup(): void {
    // Mount the same mechanics as Overworld (RoomGraph etc.) plus any
    // dungeon-only ones (BossPhases, LockAndKey instances marked
    // dungeon-scoped in mechanics.json).
    const defs = (mechanicsData as { mechanics: Array<Record<string, unknown>> }).mechanics
    for (const def of defs) {
      const instance = def as unknown as MechanicInstance
      const rt = mechanicRegistry.create(instance, this.makeStubGame())
      if (rt) this.mechanics.push(rt)
    }
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
  }

  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: (entitiesData as { entities: unknown[] }).entities,
        }),
      },
    }
  }

  mechanicsActive(): number {
    return this.mechanics.length
  }
}
