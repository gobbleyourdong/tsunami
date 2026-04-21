/**
 * Run scene — puzzle platformer roguelite.
 *
 * Heritage mix, ALL mechanics from @engine/mechanics registry:
 *   puzzle:     PuzzleObject (blocks/plates/keys/mirrors), LockAndKey
 *               (gates/doors), GatedTrigger (switch→bridge sequencing),
 *               TimeReverseMechanic (relic effect)
 *   platformer: PhysicsModifier (ice/wind per room), CameraFollow,
 *               PickupLoop (key/relic pickups), CheckpointProgression
 *               (room-entry respawn)
 *   roguelite:  ProceduralRoomChain (run-level room ordering),
 *               RoomGraph (map overview), RouteMap (branching routes),
 *               Difficulty (scales with depth)
 *   universal:  HUD, LoseOnZero
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import playerData from '../../data/player.json'
import roomsData from '../../data/rooms.json'
import relicsData from '../../data/relics.json'

export class Run {
  readonly name = 'run'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private rooms_cleared = 0

  constructor() {
    const pool = (roomsData as any).room_pool
    const relics = (relicsData as any).relics
    this.description =
      `${pool.length} room blueprints · ${Object.keys(relics).length} relics · ` +
      `${(roomsData as any).chain.length}-room runs`
  }

  setup(): void {
    const stubGame = this.makeStubGame()

    // 1. PuzzleObject — mount one per puzzle object across all rooms
    //    (puzzle heritage: the core verb-set of the genre).
    const pool = (roomsData as any).room_pool
    for (const room of pool) {
      for (const obj of (room.puzzle_objects ?? [])) {
        this.tryMount('PuzzleObject', {
          room_id: room.id,
          kind: obj.kind,
          position: obj.at,
          meta: obj,
        }, stubGame)
      }
    }

    // 2. LockAndKey — gates/doors (puzzle heritage).
    for (const room of pool) {
      for (const lock of (room.locks ?? [])) {
        this.tryMount('LockAndKey', {
          room_id: room.id,
          lock_id: lock.id,
          opens_on: lock.opens_on,
          requires_key: lock.requires_key,
        }, stubGame)
      }
    }

    // 3. GatedTrigger — timed switches, pressure plates (puzzle heritage).
    this.tryMount('GatedTrigger', {
      sources: ['switch', 'pressure_plate', 'laser_sink'],
      sequencing: 'any_required',
    }, stubGame)

    // 4. TimeReverseMechanic — the time_reversal_hourglass relic
    //    (puzzle/movement heritage — allows retries mid-frame).
    this.tryMount('TimeReverseMechanic', {
      window_sec: 2,
      cooldown_sec: 15,
      bind_relic: 'time_reversal_hourglass',
    }, stubGame)

    // 5. PhysicsModifier — per-room gravity / friction / wind
    //    (platformer heritage: same primitive as platformer Level.ts).
    this.tryMount('PhysicsModifier', {
      gravity: 1.0,
      friction: 1.0,
      per_room_overrides: pool
        .filter((r: any) => r.physics_mod)
        .map((r: any) => ({ room_id: r.id, ...r.physics_mod })),
    }, stubGame)

    // 6. CameraFollow — tracks the climber (platformer/action heritage).
    this.tryMount('CameraFollow', {
      target_tag: 'player',
      lerp: 0.2,
      deadzone: [2.0, 1.0],
    }, stubGame)

    // 7. PickupLoop — relics / keys pickup→apply (platformer heritage).
    this.tryMount('PickupLoop', {
      pickup_types: ['relic', 'key', 'health'],
      on_pickup: 'apply_and_destroy',
    }, stubGame)

    // 8. CheckpointProgression — per-room respawn (platformer heritage).
    this.tryMount('CheckpointProgression', {
      respawn_delay_sec: 0.5,
      mode: 'respawn_at_room_entry',
    }, stubGame)

    // 9. ProceduralRoomChain — run-level room ordering (roguelite heritage).
    this.tryMount('ProceduralRoomChain', {
      pool_ref: 'rooms.room_pool',
      chain_length: (roomsData as any).chain.length,
      rule: (roomsData as any).chain.rule,
      seed: 0,
    }, stubGame)

    // 10. RoomGraph — node→node map (roguelite heritage).
    this.tryMount('RoomGraph', {
      node_kind_pool: pool.map((r: any) => ({ id: r.id, tags: r.tags })),
    }, stubGame)

    // 11. RouteMap — run-overview view (roguelite heritage: Slay-the-Spire-style).
    this.tryMount('RouteMap', {
      branches_per_tier: 2,
      tiers: (roomsData as any).chain.length,
      reveal: 'next_tier_only',
    }, stubGame)

    // 12. Difficulty — scales with depth into the run (roguelite heritage).
    this.tryMount('Difficulty', {
      drive: 'rooms_cleared',
      easy: { hazard_mul: 0.8 },
      hard: { hazard_mul: 1.4 },
      max_level: 4,
    }, stubGame)

    // 13. HUD — room/relic/lives display (universal).
    this.tryMount('HUD', {
      fields: [
        { archetype: 'climber', component: 'Lives', label: 'LIVES' },
        { mechanic: 'procedural_room_chain', field: 'depth', label: 'ROOM' },
        { mechanic: 'difficulty', field: 'level', label: 'HEAT' },
      ],
      layout: 'top',
    }, stubGame)

    // 14. LoseOnZero — Lives → 0 = run ends (universal).
    this.tryMount('LoseOnZero', {
      component: 'Lives',
      on_archetype: 'climber',
    }, stubGame)
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
  }

  private tryMount(type: string, params: Record<string, unknown>, game: any): void {
    const instance = {
      id: `${type}_${this.mechanics.length}`,
      type,
      params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, game)
    if (rt) this.mechanics.push(rt)
  }

  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: [{ id: 'player_1', ...(playerData as any).player }],
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }

  /** Test: simulate clearing a room. */
  clearRoom(): void { this.rooms_cleared += 1 }

  getRunStats(): { rooms_cleared: number } {
    return { rooms_cleared: this.rooms_cleared }
  }
}
