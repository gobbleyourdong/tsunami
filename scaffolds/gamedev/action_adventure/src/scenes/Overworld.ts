/**
 * Overworld scene — action-adventure top-down exploration.
 *
 * Composes:
 *  - CameraFollow (keeps player centered with lerp+deadzone)
 *  - RoomGraph (screen-flip between overworld rooms)
 *  - HUD (health hearts + item indicators)
 *  - CheckpointProgression (on room-enter)
 *
 * Enemies and items are spawned per-room based on rooms.json[room].spawns.
 * Agent customization path: add a new room → append to rooms.json with
 * connections; add a new enemy → append to entities.json.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import entitiesData from '../../data/entities.json'
import roomsData from '../../data/rooms.json'
import itemsData from '../../data/items.json'
import mechanicsData from '../../data/mechanics.json'
import config from '../../data/config.json'

export class Overworld {
  readonly name = 'overworld'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private currentRoom: string

  constructor() {
    const rooms = (roomsData as { rooms: Record<string, unknown> }).rooms
    this.currentRoom = config.starting_room ?? Object.keys(rooms)[0]
    this.description = `${Object.keys(rooms).length} rooms · player @ ${this.currentRoom}`
  }

  setup(): void {
    // Instantiate every mechanic from mechanics.json. The genre scaffold's
    // job is the wiring; the actual runtime behavior lives in @engine/mechanics.
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

  /** Stub Game object — production scenes use the real Game harness.
   *  Exposes only what mechanics typically read during init() setup. */
  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: (entitiesData as { entities: unknown[] }).entities,
        }),
      },
      config: {
        mode: config.mode,
        width: config.width,
        height: config.height,
      },
    }
  }

  /** Get enemies/items to spawn in the current room. */
  currentRoomSpawns(): string[] {
    const rooms = (roomsData as { rooms: Record<string, { spawns?: string[] }> }).rooms
    return rooms[this.currentRoom]?.spawns ?? []
  }

  /** Public accessor for test inspection. */
  mechanicsActive(): number {
    return this.mechanics.length
  }

  /** Agent-facing helper: swap to a connected room (tests transitions). */
  transitionTo(target: string): boolean {
    const rooms = (roomsData as { rooms: Record<string, { connections?: Record<string, string> }> }).rooms
    const current = rooms[this.currentRoom]
    if (!current?.connections) return false
    const valid = Object.values(current.connections).includes(target)
    if (!valid) return false
    this.currentRoom = target
    return true
  }

  get roomId(): string { return this.currentRoom }
}
