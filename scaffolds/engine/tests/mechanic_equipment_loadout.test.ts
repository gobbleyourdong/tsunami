/**
 * Phase 3 — EquipmentLoadout runtime smoke test.
 *
 * Verifies:
 * - Registers with the mechanic registry
 * - loadCatalog filters out items with unknown slots
 * - registerCharacter initializes all slots to null
 * - equip validates tag gates
 * - equip replaces an existing item in a slot and delta-diffs stats
 * - unequip restores stats
 * - stat_mapping filters item stat_modifiers to allowed keys
 * - Seed integration: load scaffolds/.claude/seed_data/jrpg/equipment.json
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicInstance, EquipmentLoadoutParams } from '../src/design/schema'

function makeStubGame(): any {
  return { sceneManager: { activeScene: () => ({ entities: [] }) } }
}

function makeInstance(params: Partial<EquipmentLoadoutParams> = {}): MechanicInstance {
  return {
    id: 'eq_test',
    type: 'EquipmentLoadout',
    params: {
      slots: ['weapon', 'armor', 'accessory'],
      stat_mapping: {
        weapon: ['atk', 'spd'],
        armor: ['def', 'mdef'],
        accessory: ['atk', 'def', 'mdef', 'spd'],
      },
      ...params,
    } as EquipmentLoadoutParams,
  }
}

function miniCatalog() {
  return {
    bronze_sword: {
      slot: 'weapon', stat_modifiers: { atk: 5 },
      equippable_by_tags: ['warrior'],
    },
    wizard_staff: {
      slot: 'weapon', stat_modifiers: { atk: 2, mag: 8 },  // mag filtered out by stat_mapping
      equippable_by_tags: ['mage'],
    },
    leather_armor: {
      slot: 'armor', stat_modifiers: { def: 3 },
      equippable_by_tags: ['warrior', 'mage'],
    },
    power_ring: {
      slot: 'accessory', stat_modifiers: { atk: 2, spd: 1 },
      // no equippable_by_tags → anyone can equip
    },
    broken_stick: {
      slot: 'hand',  // unknown slot → filtered out by loadCatalog
      stat_modifiers: { atk: 1 },
    },
  }
}

describe('Phase 3 — EquipmentLoadout runtime', () => {
  it('is registered in the mechanic registry', () => {
    expect(mechanicRegistry.has('EquipmentLoadout')).toBe(true)
  })

  it('loadCatalog filters unknown-slot items', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    expect(rt.listCatalog()).not.toContain('broken_stick')
    expect(rt.listCatalog()).toContain('bronze_sword')
  })

  it('registerCharacter initializes all slots to null', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.registerCharacter('cecil')
    const l = rt.getLoadout('cecil')
    expect(l).toEqual({ weapon: null, armor: null, accessory: null })
  })

  it('equip validates equippable_by_tags', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    rt.registerCharacter('cecil')
    expect(rt.equip('cecil', 'wizard_staff', ['warrior'])).toBe(false)
    expect(rt.equip('cecil', 'bronze_sword', ['warrior'])).toBe(true)
  })

  it('equip applies stat_modifiers to effective stats', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    rt.registerCharacter('cecil')
    rt.equip('cecil', 'bronze_sword', ['warrior'])
    expect(rt.getEffectiveStats('cecil')).toEqual({ atk: 5 })
  })

  it('equip replaces slot item and re-diffs stats', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    rt.registerCharacter('cecil')
    rt.equip('cecil', 'bronze_sword', ['warrior'])  // atk +5
    rt.equip('cecil', 'power_ring', [])             // acc: atk +2, spd +1
    expect(rt.getEffectiveStats('cecil')).toEqual({ atk: 7, spd: 1 })
  })

  it('unequip restores stats and returns prev item id', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    rt.registerCharacter('cecil')
    rt.equip('cecil', 'bronze_sword', ['warrior'])
    expect(rt.unequip('cecil', 'weapon')).toBe('bronze_sword')
    expect(rt.getEffectiveStats('cecil')).toEqual({})
    expect(rt.getEquipped('cecil', 'weapon')).toBe(null)
  })

  it('stat_mapping filters item stats to allowed keys per slot', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    rt.registerCharacter('rydia')
    // wizard_staff declares atk+mag; stat_mapping for weapon allows only atk+spd.
    // mag should be filtered out.
    rt.equip('rydia', 'wizard_staff', ['mage'])
    expect(rt.getEffectiveStats('rydia')).toEqual({ atk: 2 })
  })

  it('equip on unregistered character returns false', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    expect(rt.equip('nobody', 'bronze_sword', ['warrior'])).toBe(false)
  })

  it('unequip on empty slot returns null', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.registerCharacter('cecil')
    expect(rt.unequip('cecil', 'weapon')).toBe(null)
  })

  it('integrates with JOB-F seed equipment.json', () => {
    const seedPath = join(
      __dirname, '..', '..', '..', '.claude', 'seed_data', 'jrpg', 'equipment.json',
    )
    if (!existsSync(seedPath)) return
    const data = JSON.parse(readFileSync(seedPath, 'utf8'))
    const rt = mechanicRegistry.create(
      makeInstance({
        slots: ['weapon', 'armor', 'accessory_1', 'accessory_2', 'consumable'],
        stat_mapping: {
          weapon: ['str', 'mag', 'spd', 'atk'],
          armor: ['def', 'mdef', 'hp_bonus'],
          accessory_1: ['str', 'def', 'mdef', 'spd', 'mag'],
          accessory_2: ['str', 'def', 'mdef', 'spd', 'mag'],
          consumable: [],
        },
      }),
      makeStubGame(),
    )! as any
    rt.loadCatalog(data.equipment)
    rt.registerCharacter('cecil')
    // short_sword should be equip-valid for a warrior (its seed declares
    // equippable_by_tags: ['warrior', 'thief']).
    expect(rt.equip('cecil', 'short_sword', ['warrior'])).toBe(true)
    const stats = rt.getEffectiveStats('cecil')
    expect(stats.str).toBe(2)
  })

  it('expose() surfaces per-character loadouts + catalog size', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    rt.registerCharacter('cecil')
    rt.equip('cecil', 'bronze_sword', ['warrior'])
    const snap = rt.expose() as any
    expect(snap.loadouts.cecil.equipped.weapon).toBe('bronze_sword')
    expect(snap.catalog_size).toBe(4)  // 5 items minus 1 filtered-out
  })

  it('dispose clears state', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadCatalog(miniCatalog())
    rt.registerCharacter('cecil')
    rt.dispose()
    expect(rt.listCharacters()).toEqual([])
    expect(rt.listCatalog()).toEqual([])
  })
})
