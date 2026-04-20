// EquipmentLoadout — Phase 3 JRPG mechanic (v1.2).
//
// Per-character slot loadout. A character has N slots (weapon / armor /
// accessory / etc.) defined in params. Equipping an item puts it in a
// slot, unequipping removes it, and the runtime tracks cumulative stat
// deltas per character so combat / HUD / save-systems can read the
// effective stats off a single `getEffectiveStats(characterId)` call.
//
// Params from catalog:
// - slots: ordered slot ids (e.g. ['weapon','head','body','acc1','acc2'])
// - stat_mapping: slot_id → list of stat keys that items in this slot
//   may modify (used only to validate incoming items — the mechanic
//   applies whatever stat_modifiers the item carries, filtered by
//   the slot's allowed keys).
//
// Items (loaded from scaffold data/equipment.json shape — see
// scaffolds/.claude/seed_data/jrpg/equipment.json):
// - id, slot, stat_modifiers: { [stat]: delta }, equippable_by_tags: []
//
// Characters pass a tags list to equip() so equippable_by_tags gates
// the equip at call time.

import type { Game } from '../../game/game'
import type { EquipmentLoadoutParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

interface EquipItem {
  id: string
  slot: string
  stat_modifiers?: Record<string, number>
  equippable_by_tags?: string[]
  [k: string]: unknown
}

interface Loadout {
  /** slot_id → item_id currently equipped. */
  equipped: Record<string, string | null>
  /** Current cumulative stat deltas from all equipped items. */
  stat_deltas: Record<string, number>
}

class EquipmentLoadoutRuntime implements MechanicRuntime {
  private params: EquipmentLoadoutParams
  private game!: Game
  private loadouts = new Map<string, Loadout>()
  private catalog = new Map<string, EquipItem>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as EquipmentLoadoutParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* state-only mechanic */ }

  dispose(): void {
    this.loadouts.clear()
    this.catalog.clear()
  }

  expose(): Record<string, unknown> {
    const snapshot: Record<string, unknown> = {}
    for (const [id, l] of this.loadouts) {
      snapshot[id] = {
        equipped: { ...l.equipped },
        stat_deltas: { ...l.stat_deltas },
      }
    }
    return { loadouts: snapshot, catalog_size: this.catalog.size }
  }

  // ---- Public API ----

  /** Load the item catalog — scaffold typically passes the contents
   *  of data/equipment.json. Items are validated against the slots +
   *  stat_mapping from params. */
  loadCatalog(items: Record<string, EquipItem>): void {
    this.catalog.clear()
    for (const [id, item] of Object.entries(items)) {
      if (!this.params.slots.includes(item.slot)) continue  // unknown slot; skip
      this.catalog.set(id, { ...item, id })
    }
  }

  /** Register a character so its slots initialize to null. */
  registerCharacter(characterId: string): void {
    if (this.loadouts.has(characterId)) return
    const slots: Record<string, string | null> = {}
    for (const s of this.params.slots) slots[s] = null
    this.loadouts.set(characterId, { equipped: slots, stat_deltas: {} })
  }

  /** Equip an item into the character's slot. Returns false if:
   *  - item unknown, or
   *  - character tags don't satisfy equippable_by_tags, or
   *  - the character isn't registered yet.
   *  If the slot already has an item, that item is unequipped
   *  implicitly (the returned-to-inventory behavior is scaffold-side). */
  equip(characterId: string, itemId: string, characterTags: string[]): boolean {
    const loadout = this.loadouts.get(characterId)
    if (!loadout) return false
    const item = this.catalog.get(itemId)
    if (!item) return false
    if (item.equippable_by_tags && item.equippable_by_tags.length > 0) {
      const allowed = item.equippable_by_tags.some((t) => characterTags.includes(t))
      if (!allowed) return false
    }
    const slot = item.slot
    // Remove previous item's deltas from the slot first.
    const prev = loadout.equipped[slot]
    if (prev) this.applyDelta(loadout, this.catalog.get(prev), -1)
    loadout.equipped[slot] = itemId
    this.applyDelta(loadout, item, +1)
    try { writeWorldFlag(this.game, `equip.${characterId}.${slot}`, itemId) } catch { /* ignore */ }
    return true
  }

  /** Unequip the slot. Returns the previous item id (if any). */
  unequip(characterId: string, slot: string): string | null {
    const loadout = this.loadouts.get(characterId)
    if (!loadout) return null
    if (!this.params.slots.includes(slot)) return null
    const prevId = loadout.equipped[slot]
    if (!prevId) return null
    const prev = this.catalog.get(prevId)
    this.applyDelta(loadout, prev, -1)
    loadout.equipped[slot] = null
    try { writeWorldFlag(this.game, `equip.${characterId}.${slot}`, null) } catch { /* ignore */ }
    return prevId
  }

  /** Return the cumulative stat_deltas for a character's current loadout. */
  getEffectiveStats(characterId: string): Record<string, number> {
    const loadout = this.loadouts.get(characterId)
    return loadout ? { ...loadout.stat_deltas } : {}
  }

  /** Return the item currently in a slot (or null). */
  getEquipped(characterId: string, slot: string): string | null {
    return this.loadouts.get(characterId)?.equipped[slot] ?? null
  }

  /** Return the whole per-slot map for a character. */
  getLoadout(characterId: string): Record<string, string | null> {
    const l = this.loadouts.get(characterId)
    return l ? { ...l.equipped } : {}
  }

  listCatalog(): string[] { return [...this.catalog.keys()] }
  listCharacters(): string[] { return [...this.loadouts.keys()] }
  getItem(id: string): EquipItem | undefined {
    const i = this.catalog.get(id)
    return i ? { ...i } : undefined
  }

  // ---- Internals ----

  private applyDelta(loadout: Loadout, item: EquipItem | undefined, sign: 1 | -1): void {
    if (!item || !item.stat_modifiers) return
    const allowedKeys = this.params.stat_mapping?.[item.slot]
    for (const [stat, delta] of Object.entries(item.stat_modifiers)) {
      // If stat_mapping declares allowed keys for this slot, filter to them.
      if (allowedKeys && allowedKeys.length > 0 && !allowedKeys.includes(stat)) continue
      loadout.stat_deltas[stat] = (loadout.stat_deltas[stat] ?? 0) + sign * delta
      if (loadout.stat_deltas[stat] === 0) delete loadout.stat_deltas[stat]
    }
  }
}

mechanicRegistry.register('EquipmentLoadout', (instance, game) => {
  const rt = new EquipmentLoadoutRuntime(instance)
  rt.init(game)
  return rt
})
