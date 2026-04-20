/**
 * Battle scene — the ATB combat loop.
 *
 * Composes mechanics from @engine/mechanics:
 *  - ATBCombat (per-actor real-time meter fill, command queue)
 *  - PartyComposition (active party — consumed by ATB to build combatants)
 *  - LevelUpProgression (XP grant on victory)
 *  - HUD (per-party ATB bars + HP + MP + enemy HP)
 *  - LoseOnZero (all-party-HP=0 → defeat)
 *
 * Enters on World's encounter roll; returns to World on victory / fled.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import partyData from '../../data/party.json'
import battlesData from '../../data/battles.json'
import spellsData from '../../data/spells.json'
import config from '../../data/config.json'

export class Battle {
  readonly name = 'battle'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private atbRuntime: any = null
  private levelRuntime: any = null
  private encounterGroup: string | null = null

  constructor() {
    const grunts = Object.keys((battlesData as any).enemies ?? {})
    const spells = Object.keys((spellsData as any).spells ?? {})
    this.description = `ATB battle — ${grunts.length} enemies + ${spells.length} spells in catalog`
  }

  setup(): void {
    // ATBCombat — real-time meter loop.
    this.atbRuntime = this.tryMount('ATBCombat', {
      party_size: 4,
      atb_speed: 1.0,
      command_menu: ['attack', 'magic', 'item', 'defend'],
      can_swap_rows: false,
    })

    // LevelUpProgression — XP on victory feeds this.
    this.levelRuntime = this.tryMount('LevelUpProgression', {
      xp_curve: 'quadratic',
      base_xp: 100,
      stat_gains: { hp: 8, mp: 3, atk: 1, def: 1 },
      learn_at_level: { 5: 'fire', 10: 'blizzard', 15: 'cure', 20: 'curaga' },
      max_level: 99,
    })

    this.tryMount('HUD', {
      fields: [
        { mechanic: 'atb_combat', field: 'atb_meters', label: 'ATB' },
        { archetype: 'party', component: 'Health', label: 'HP' },
        { archetype: 'party', component: 'Mana', label: 'MP' },
        { archetype: 'enemies', component: 'Health', label: 'Enemy HP' },
      ],
      layout: 'bottom',
    })

    this.tryMount('LoseOnZero', {
      watch_archetype: 'party',
      watch_component: 'Health',
      aggregate: 'all_zero',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
    this.atbRuntime = null
    this.levelRuntime = null
  }

  /** Public API — called when World rolls an encounter. */
  startEncounter(groupId: string, partyIds: string[]): void {
    this.encounterGroup = groupId
    const partyRecords = (partyData as any).characters ?? (partyData as any).party ?? {}
    const enemies = (battlesData as any).enemies ?? {}
    const groups = (battlesData as any).encounter_groups ?? {}
    const group = groups[groupId] ?? { members: Object.keys(enemies).slice(0, 1) }

    const partyCombatants = partyIds.map((id) => {
      const m = partyRecords[id] ?? {}
      return {
        id, team: 'party' as const,
        hp: m.hp ?? 100, hp_max: m.hp ?? 100,
        speed: m.speed ?? 8, atb: 0, ko: false,
      }
    })
    const enemyCombatants = (group.members ?? []).map((eid: string) => {
      const e = enemies[eid] ?? {}
      return {
        id: eid, team: 'enemy' as const,
        hp: e.hp ?? 20, hp_max: e.hp ?? 20,
        speed: e.speed ?? 4, atb: 0, ko: false,
      }
    })
    this.atbRuntime?.startCombat?.(partyCombatants, enemyCombatants)
  }

  /** Public API — after victory, grant XP to each party member. */
  grantVictoryXP(amount: number, partyIds: string[]): void {
    for (const id of partyIds) {
      this.levelRuntime?.grantXP?.(id, amount)
    }
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
      config: { mode: '2d', combat_style: (config as any).combat_style ?? 'atb' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
