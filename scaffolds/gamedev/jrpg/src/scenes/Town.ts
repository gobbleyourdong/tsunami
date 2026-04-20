/**
 * Town scene — safe hub with shops + NPCs + inn.
 *
 * Composes mechanics from @engine/mechanics:
 *  - Shop (inventory-for-gold per JRPG convention)
 *  - DialogTree (NPC conversation branches)
 *  - EquipmentLoadout (party members swap gear at equip menu)
 *  - HUD (gold, party HP, active region label)
 *
 * Hands off back to World when the player exits.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import equipmentData from '../../data/equipment.json'
import partyData from '../../data/party.json'
import config from '../../data/config.json'

export class Town {
  readonly name = 'town'
  description = 'Town hub — shop, inn, equip menu'
  private mechanics: MechanicRuntime[] = []
  private equipRuntime: any = null

  setup(): void {
    // EquipmentLoadout — load 15 items from JOB-F seed.
    this.equipRuntime = this.tryMount('EquipmentLoadout', {
      slots: ['weapon', 'armor', 'accessory_1', 'accessory_2', 'consumable'],
      stat_mapping: {
        weapon: ['str', 'mag', 'spd', 'atk'],
        armor: ['def', 'mdef', 'hp_bonus'],
        accessory_1: ['str', 'def', 'mdef', 'spd', 'mag'],
        accessory_2: ['str', 'def', 'mdef', 'spd', 'mag'],
        consumable: [],
      },
    })
    if (this.equipRuntime && typeof this.equipRuntime.loadCatalog === 'function') {
      this.equipRuntime.loadCatalog((equipmentData as any).equipment)
      // Pre-register the starting party so the equip menu has rows ready.
      const members = (partyData as any).characters ?? (partyData as any).party ?? {}
      const starting = (config as any).starting_party ?? Object.keys(members).slice(0, 4)
      for (const id of starting) {
        this.equipRuntime.registerCharacter?.(id)
      }
    }

    // Shop — buy/sell gated by gold, reads equipment.json for inventory.
    this.tryMount('Shop', {
      inventory: Object.keys((equipmentData as any).equipment).slice(0, 8),
      currency: 'gold',
      open_on_enter: false,
    })

    // DialogTree — canonical JRPG innkeeper / shopkeeper lines.
    this.tryMount('DialogTree', {
      root_node: 'innkeeper_welcome',
      branches_ref: 'data/dialog.json',
      portrait_slot: 'npc',
    })

    this.tryMount('HUD', {
      fields: [
        { singleton: 'gold', label: 'GP' },
        { mechanic: 'world_map_travel', field: 'current_region', label: 'TOWN' },
      ],
      layout: 'corners',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
    this.equipRuntime = null
  }

  /** Public API — called from scene-manager when the player enters the equip menu. */
  equipItem(characterId: string, itemId: string, characterTags: string[]): boolean {
    return this.equipRuntime?.equip?.(characterId, itemId, characterTags) ?? false
  }

  getEffectiveStats(characterId: string): Record<string, number> {
    return this.equipRuntime?.getEffectiveStats?.(characterId) ?? {}
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
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
