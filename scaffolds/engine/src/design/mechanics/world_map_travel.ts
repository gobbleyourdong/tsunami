// WorldMapTravel — Phase 3 JRPG mechanic (v1.2).
//
// Scene-to-scene overworld navigation. Maintains a region graph,
// the party's current region, unlocked vehicles, and per-step
// random-encounter rolls. Distinct from RoomGraph (room-to-room
// within a single scene); this is scene-level with travel semantics.
//
// Corpus heritage (JOB-A + JOB-N refresh): DQ3 (1988), FF1+ (1987),
// Chrono Trigger time-portal (1995). Sister's JOB-F seed uses this
// to wire 8 FF4-flavored regions (Baron → Mist → Kaipo → Antlion →
// overworld → Zeromus Castle) with encounter tables + vehicle gates.

import type { Game } from '../../game/game'
import type { WorldMapTravelParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

interface Region {
  id: string
  /** Scene ids adjacent to this region. */
  connections: string[]
  /** Base encounter probability [0..1] — 0 disables encounters. */
  encounter_rate?: number
  /** Enemy ids rolled on encounter. */
  encounter_table?: string[]
  /** Vehicle id required to traverse INTO this region. null = walk. */
  requires_vehicle?: string | null
  /** Free-form metadata — scaffold reads these in scene code. */
  [k: string]: unknown
}

interface Graph {
  regions: Record<string, Region>
}

interface TravelEvent {
  kind: 'move' | 'encounter' | 'blocked'
  from?: string
  to?: string
  enemy?: string
  reason?: string
}

class WorldMapTravelRuntime implements MechanicRuntime {
  private params: WorldMapTravelParams
  private game!: Game
  private graph: Graph = { regions: {} }
  private currentRegion: string = ''
  private unlockedVehicles = new Set<string>()
  private activeVehicle: string | null = null
  private events: TravelEvent[] = []
  /** Injectable RNG — deterministic tests override this. Default = Math.random. */
  private rng: () => number = Math.random

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as WorldMapTravelParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* event-driven; no per-frame work */ }

  dispose(): void {
    this.graph = { regions: {} }
    this.currentRegion = ''
    this.unlockedVehicles.clear()
    this.activeVehicle = null
    this.events.length = 0
  }

  expose(): Record<string, unknown> {
    return {
      current_region: this.currentRegion,
      unlocked_vehicles: [...this.unlockedVehicles],
      active_vehicle: this.activeVehicle,
      reachable: this.reachableFromCurrent(),
      last_event: this.events[this.events.length - 1] ?? null,
      region_count: Object.keys(this.graph.regions).length,
    }
  }

  // ---- Public API ----

  /** Load the region graph — scaffold typically calls this at scene init
   *  with the contents of data/world_map.json. */
  loadGraph(graph: Graph, startingRegion?: string): void {
    this.graph = graph
    if (startingRegion && graph.regions[startingRegion]) {
      this.currentRegion = startingRegion
    }
  }

  /** Travel to a connected region. Returns false if the edge doesn't
   *  exist, the destination requires an unowned vehicle, or the graph
   *  is unloaded. `teleport_menu` mode skips the adjacency check but
   *  still honors vehicle gates. */
  travelTo(destination: string): boolean {
    const to = this.graph.regions[destination]
    if (!to) {
      this.events.push({ kind: 'blocked', to: destination, reason: 'unknown_region' })
      return false
    }

    const reqVehicle = to.requires_vehicle
    if (reqVehicle && !this.unlockedVehicles.has(reqVehicle)) {
      this.events.push({ kind: 'blocked', to: destination, reason: 'vehicle_required' })
      return false
    }

    if (this.params.map_mode !== 'teleport_menu') {
      const from = this.graph.regions[this.currentRegion]
      if (!from || !from.connections.includes(destination)) {
        this.events.push({
          kind: 'blocked', from: this.currentRegion, to: destination, reason: 'not_connected',
        })
        return false
      }
    }

    const prev = this.currentRegion
    this.currentRegion = destination
    this.events.push({ kind: 'move', from: prev, to: destination })

    try { writeWorldFlag(this.game, 'world.current_region', destination) } catch { /* ignore */ }

    // Roll for random encounter on walkable destinations.
    this.rollEncounter(destination)
    return true
  }

  /** Unlock a vehicle (e.g. "airship" awarded after a boss fight). */
  unlockVehicle(id: string): boolean {
    if (!this.params.vehicles?.includes(id)) return false
    this.unlockedVehicles.add(id)
    try { writeWorldFlag(this.game, `world.vehicle_unlocked.${id}`, true) } catch { /* ignore */ }
    return true
  }

  boardVehicle(id: string): boolean {
    if (!this.unlockedVehicles.has(id)) return false
    this.activeVehicle = id
    return true
  }

  disembark(): void { this.activeVehicle = null }

  setRNG(rng: () => number): void { this.rng = rng }

  // ---- Read API ----

  getCurrentRegion(): string { return this.currentRegion }
  getRegion(id: string): Region | undefined { return this.graph.regions[id] }
  listRegions(): string[] { return Object.keys(this.graph.regions) }
  reachableFromCurrent(): string[] {
    if (this.params.map_mode === 'teleport_menu') {
      // Every region the party can reach (honors vehicle gates).
      return Object.entries(this.graph.regions)
        .filter(([_id, r]) => !r.requires_vehicle || this.unlockedVehicles.has(r.requires_vehicle))
        .map(([id]) => id)
    }
    const here = this.graph.regions[this.currentRegion]
    return here ? [...here.connections] : []
  }
  getEvents(): TravelEvent[] { return [...this.events] }
  getUnlockedVehicles(): string[] { return [...this.unlockedVehicles] }
  getActiveVehicle(): string | null { return this.activeVehicle }
  getMode(): WorldMapTravelParams['map_mode'] { return this.params.map_mode }

  // ---- Internals ----

  private rollEncounter(region: string): void {
    const r = this.graph.regions[region]
    if (!r) return
    // On vehicle: skip encounter (classic JRPG convention — airship is safe).
    if (this.activeVehicle) return
    const baseRate = r.encounter_rate ?? this.params.encounter_rate
    if (baseRate <= 0) return
    if (!r.encounter_table || r.encounter_table.length === 0) return
    if (this.rng() >= baseRate) return
    const enemy = r.encounter_table[Math.floor(this.rng() * r.encounter_table.length)]
    this.events.push({ kind: 'encounter', to: region, enemy })
    try { writeWorldFlag(this.game, 'world.encounter_rolled', enemy) } catch { /* ignore */ }
  }
}

mechanicRegistry.register('WorldMapTravel', (instance, game) => {
  const rt = new WorldMapTravelRuntime(instance)
  rt.init(game)
  return rt
})
