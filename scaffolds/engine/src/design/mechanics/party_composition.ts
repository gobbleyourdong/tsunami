// PartyComposition — Phase 3 JRPG mechanic (v1.2).
//
// Roster + active-party + formation manager. Characters sit in a
// roster pool (recruited members); a subset are "active" (battle-
// visible, max_active); the rest are "reserve". A formation maps
// active slots to roles / rows for rendering + combat positioning.
//
// Combat mechanics (ATBCombat / TurnBasedCombat) declare this as
// `needs_mechanic_types: ['PartyComposition']` — they query the
// active roster to build their combatant list. Swaps mid-battle
// are gated by `can_swap_mid_battle` (FF10 mechanic).

import type { Game } from '../../game/game'
import type { PartyCompositionParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

interface Member {
  id: string
  /** Free-form class / job label — 'warrior' | 'mage' | etc. */
  role: string
  /** Current battle row — overrides formation default if set. */
  row?: 'front' | 'back'
}

class PartyCompositionRuntime implements MechanicRuntime {
  private params: PartyCompositionParams
  private game!: Game
  private roster = new Map<string, Member>()
  private active: string[] = []           // ordered slot assignment
  private formation: string
  private battleLocked = false            // set by startBattle(), cleared by endBattle()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as PartyCompositionParams
    this.formation = this.params.default_formation
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* state-only mechanic — no per-frame work */ }

  dispose(): void {
    this.roster.clear()
    this.active.length = 0
    this.battleLocked = false
  }

  expose(): Record<string, unknown> {
    const all = [...this.roster.keys()]
    return {
      active_party: [...this.active],
      reserve_party: all.filter((id) => !this.active.includes(id)),
      formation: this.formation,
      roster_size: this.roster.size,
      active_size: this.active.length,
      battle_locked: this.battleLocked,
    }
  }

  // ---- Public API ----

  /** Add a member to the roster. Rejects if the roster is full. */
  addToRoster(id: string, role: string, row: 'front' | 'back' = 'front'): boolean {
    if (this.roster.size >= this.params.max_roster) return false
    if (this.roster.has(id)) return false
    this.roster.set(id, { id, role, row })
    return true
  }

  /** Remove a member entirely (e.g. a party member permanently leaves). */
  removeFromRoster(id: string): boolean {
    if (this.battleLocked && this.active.includes(id)) return false
    const removed = this.roster.delete(id)
    this.active = this.active.filter((a) => a !== id)
    return removed
  }

  /** Replace active slot `index` with `id` from the reserve. */
  setActive(index: number, id: string): boolean {
    if (index < 0 || index >= this.params.max_active) return false
    if (!this.roster.has(id)) return false
    if (this.battleLocked && !this.params.can_swap_mid_battle) return false
    // If the new member was already active in another slot, move them.
    const existing = this.active.indexOf(id)
    if (existing !== -1) this.active[existing] = this.active[index] ?? ''
    this.active[index] = id
    // Trim any empty-string slot left by the swap.
    this.active = this.active.filter((a) => a !== '')
    return true
  }

  /** Swap two members: one active, one reserve. Rejects mid-battle
   *  unless `can_swap_mid_battle` is true. */
  swapInOut(activeId: string, reserveId: string): boolean {
    if (this.battleLocked && !this.params.can_swap_mid_battle) return false
    const slot = this.active.indexOf(activeId)
    if (slot === -1) return false
    if (!this.roster.has(reserveId)) return false
    if (this.active.includes(reserveId)) return false
    this.active[slot] = reserveId
    return true
  }

  /** Pick active members by id list (ordered). Rejects if count
   *  exceeds max_active or any id isn't in the roster. */
  setActiveParty(ids: string[]): boolean {
    if (ids.length > this.params.max_active) return false
    if (this.battleLocked && !this.params.can_swap_mid_battle) return false
    for (const id of ids) if (!this.roster.has(id)) return false
    // Reject duplicates.
    if (new Set(ids).size !== ids.length) return false
    this.active = [...ids]
    return true
  }

  setFormation(id: string): void {
    const prev = this.formation
    this.formation = id
    if (prev !== id) {
      try { writeWorldFlag(this.game, 'party.formation_changed', id) } catch { /* ignore */ }
    }
  }

  setRow(memberId: string, row: 'front' | 'back'): boolean {
    const m = this.roster.get(memberId)
    if (!m) return false
    m.row = row
    return true
  }

  /** Combat mechanics call startBattle() when combat begins; swaps
   *  become gated by can_swap_mid_battle until endBattle() fires. */
  startBattle(): void {
    this.battleLocked = true
    try { writeWorldFlag(this.game, 'party.in_battle', true) } catch { /* ignore */ }
  }

  endBattle(): void {
    this.battleLocked = false
    try { writeWorldFlag(this.game, 'party.in_battle', false) } catch { /* ignore */ }
  }

  // ---- Read API ----

  getActive(): string[] { return [...this.active] }
  getReserve(): string[] { return [...this.roster.keys()].filter((id) => !this.active.includes(id)) }
  getRoster(): string[] { return [...this.roster.keys()] }
  getMember(id: string): Member | undefined {
    const m = this.roster.get(id)
    return m ? { ...m } : undefined
  }
  getFormation(): string { return this.formation }
  isBattleLocked(): boolean { return this.battleLocked }
}

mechanicRegistry.register('PartyComposition', (instance, game) => {
  const rt = new PartyCompositionRuntime(instance)
  rt.init(game)
  return rt
})
