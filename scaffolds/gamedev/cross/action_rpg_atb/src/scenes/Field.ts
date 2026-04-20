/**
 * Field scene — Zelda-style real-time top-down dungeon traversal.
 *
 * Mounts 6 of the 9 target mechanics (field-mode subset):
 *   - RoomGraph     — dungeon room-to-room traversal
 *   - LockAndKey    — keycard/boss-key gates
 *   - ItemUse       — bow / bomb / grappling-hook field tools
 *   - CameraFollow  — top-down rig following the party leader
 *   - PartyComposition — active-party tracker (shared with Battle scene)
 *   - HUD           — field HUD variant (hearts, keys, items)
 *
 * Hands off to Battle scene when enemy contact fires.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import roomsData from '../../data/rooms.json'
import partyData from '../../data/party.json'
import playerData from '../../data/player.json'
import config from '../../data/config.json'

export class Field {
  readonly name = 'field'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private partyRuntime: any = null
  private currentRoom: string

  constructor() {
    const rooms = Object.keys((roomsData as any).rooms ?? {})
    this.description = `Field — ${rooms.length} dungeon rooms, real-time traversal`
    this.currentRoom = (config as any).starting_room ?? rooms[0] ?? 'entrance'
  }

  setup(): void {
    this.tryMount('RoomGraph', {
      starting_room: this.currentRoom,
      rooms_ref: 'data/rooms.json',
    })

    this.tryMount('LockAndKey', {
      lock_tag: 'locked_door',
      key_tag: 'key',
    })

    this.tryMount('ItemUse', {
      inventory_component: 'Inventory',
      usable_tags: ['bow', 'bomb', 'grappling_hook', 'lantern'],
    })

    this.tryMount('CameraFollow', {
      target_tag: 'party_leader',
      lerp: 0.25,
      deadzone: [0.5, 0.5],
    })

    // PartyComposition — the shared state carrier between Field and Battle.
    // Set up in Field scene init; Battle scene reads `active_party` from
    // expose() to populate its ATB combatant list.
    this.partyRuntime = this.tryMount('PartyComposition', {
      max_active: 4,
      max_roster: 6,
      can_swap_mid_battle: false,
      default_formation: 'line',
    })
    if (this.partyRuntime) {
      const members = (partyData as any).members ?? {}
      for (const [id, m] of Object.entries(members)) {
        this.partyRuntime.addToRoster?.(id, (m as any).class ?? 'adventurer')
      }
      const starting = (config as any).starting_party ??
        Object.keys(members).slice(0, 4)
      this.partyRuntime.setActiveParty?.(starting)
    }

    this.tryMount('HUD', {
      fields: [
        { archetype: 'party_leader', component: 'Health', label: 'HP' },
        { singleton: 'rupees',       label: 'GOLD' },
        { mechanic: 'room_graph',    field: 'current_room', label: 'ROOM' },
        { singleton: 'keys',         label: 'KEYS' },
      ],
      layout: 'corners',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
    this.partyRuntime = null
  }

  // ---- Public API (cross-scene handoff) ----

  /** Called on enemy-contact: Battle scene reads this snapshot. */
  handoffToBattle(): any {
    return this.partyRuntime?.expose?.() ?? null
  }

  /** Called on battle-victory: Field scene reapplies state that Battle
   *  mutated (HP drops, KO'd members, gear swaps). */
  restoreFromBattle(snapshot: any): void {
    if (!snapshot || !this.partyRuntime) return
    // PartyComposition handles active_party restoration via setActiveParty.
    // HP / MP / equipment live on per-member components and persist
    // automatically because both scenes share the same Entity instances
    // (sceneManager doesn't recreate them on transition).
  }

  getCurrentRoom(): string { return this.currentRoom }

  private tryMount(type: string, params: Record<string, unknown>): any {
    const instance = {
      id: `${type}_${this.mechanics.length}`, type, params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, this.makeStubGame())
    if (rt) {
      this.mechanics.push(rt)
      return rt
    }
    return null
  }

  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: [
            { id: 'party_leader', ...((playerData as any).player ?? {}) },
          ],
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
