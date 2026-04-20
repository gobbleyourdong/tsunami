/**
 * Battle scene — FF4-style ATB combat.
 *
 * Mounts the battle-mode subset of the 9 target mechanics:
 *   - ATBCombat          — real-time ATB meter loop
 *   - PartyComposition   — ***SHARED with Field scene*** (same runtime
 *                           instance read via world-flags / scene-manager
 *                           for the canary's persistence invariant)
 *   - EquipmentLoadout   — per-member slot-stat modifiers (carry into
 *                           combat from Field's equip menu)
 *   - BossPhases         — multi-phase boss fights for story bosses
 *   - CameraFollow       — dual-mode camera (orthographic facing enemies)
 *   - HUD                — battle HUD variant (ATB bars + cmd menu)
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import battlesData from '../../data/battles.json'
import partyData from '../../data/party.json'
import equipmentData from '../../data/equipment.json'
import config from '../../data/config.json'

export class Battle {
  readonly name = 'battle'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private atbRuntime: any = null
  private equipRuntime: any = null

  constructor() {
    const encounters = Object.keys((battlesData as any).encounter_groups ?? {})
    this.description = `Battle — ${encounters.length} encounter groups, ATB combat`
  }

  setup(): void {
    // ATBCombat — real-time meter loop.
    this.atbRuntime = this.tryMount('ATBCombat', {
      party_size: 4,
      atb_speed: 1.0,
      command_menu: ((partyData as any).battle_command_menu) ??
                    ['attack', 'magic', 'item', 'defend'],
      can_swap_rows: false,
    })

    // PartyComposition re-mounted in Battle — same scaffold-wide
    // world-flag state means it reads active_party set by Field.
    // (In production, a single PartyComposition runtime would be
    // re-parented across scenes via SceneManager — this scaffold
    // shows the composition pattern.)
    this.tryMount('PartyComposition', {
      max_active: 4,
      max_roster: 6,
      can_swap_mid_battle: false,
      default_formation: 'battle_line',
    })

    // EquipmentLoadout — persists stat deltas set in Field's equip menu.
    this.equipRuntime = this.tryMount('EquipmentLoadout', {
      slots: ['weapon', 'armor', 'accessory'],
      stat_mapping: {
        weapon: ['atk', 'mag'],
        armor: ['def', 'mdef', 'hp_bonus'],
        accessory: ['atk', 'def', 'spd'],
      },
    })
    if (this.equipRuntime) {
      this.equipRuntime.loadCatalog?.((equipmentData as any).equipment ?? {})
      const members = (partyData as any).members ?? {}
      const starting = (config as any).starting_party ?? Object.keys(members).slice(0, 4)
      for (const id of starting) this.equipRuntime.registerCharacter?.(id)
    }

    // BossPhases — story bosses use this.
    this.tryMount('BossPhases', {
      boss_archetype_tag: 'boss',
      phase_triggers: 'hp_threshold',
    })

    this.tryMount('CameraFollow', {
      target_tag: 'battle_anchor',
      lerp: 0.1,
      deadzone: [0.2, 0.2],
    })

    this.tryMount('HUD', {
      fields: [
        { mechanic: 'atb_combat',   field: 'atb_meters',  label: 'ATB' },
        { archetype: 'party_member', component: 'Health', label: 'HP' },
        { archetype: 'party_member', component: 'Mana',   label: 'MP' },
        { archetype: 'enemy',        component: 'Health', label: 'Enemy HP' },
      ],
      layout: 'bottom',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
    this.atbRuntime = null
    this.equipRuntime = null
  }

  // ---- Public API (cross-scene handoff) ----

  startEncounter(groupId: string, partyIds: string[]): void {
    const groups = (battlesData as any).encounter_groups ?? {}
    const actors = (battlesData as any).battle_actors ?? {}
    const group = groups[groupId] ?? { members: [] }
    const members = (partyData as any).members ?? {}

    const partyCombatants = partyIds.map((id) => {
      const m = members[id] ?? {}
      return {
        id, team: 'party' as const,
        hp: m.hp ?? 100, hp_max: m.hp ?? 100,
        speed: m.speed ?? 8, atb: 0, ko: false,
      }
    })
    const enemyCombatants = (group.members ?? []).map((eid: string) => {
      const e = actors[eid] ?? {}
      return {
        id: eid, team: 'enemy' as const,
        hp: e.hp ?? 25, hp_max: e.hp ?? 25,
        speed: e.speed ?? 4, atb: 0, ko: false,
      }
    })
    this.atbRuntime?.startCombat?.(partyCombatants, enemyCombatants)
  }

  /** After victory, return the per-member HP/MP snapshot for Field to absorb. */
  snapshotForField(): any {
    return this.atbRuntime?.expose?.() ?? null
  }

  getOutcome(): string {
    return this.atbRuntime?.getOutcome?.() ?? 'ongoing'
  }

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
      sceneManager: { activeScene: () => ({ entities: [] }) },
      config: { mode: '2d', combat_style: 'atb' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
