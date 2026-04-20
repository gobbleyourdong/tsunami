// RoleAssignment — v1.3 role extension (Cycle 26).
//
// Runtime role → entity mapping. The scaffold declares a set of role
// ids (e.g. 'player_controlled', 'leader', 'healer', 'scout'), and the
// mechanic tracks which entity currently holds each role. Reassignment
// is idempotent on repeat-assignment but steals the role from the
// prior holder unless `allow_multi_role=true`.
//
// Use cases:
//   - Lost Vikings: player_controlled role swaps between Erik/Baleog/Olaf
//   - Lemmings: dig/build/bash role assigned to an available lemming
//   - LBP drop-in multiplayer: player_N role claimed by newly-joined pad
//   - RTS: squad-leader role bounces to a surviving unit on death

import type { Game } from '../../game/game'
import type { RoleAssignmentParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

class RoleAssignmentRuntime implements MechanicRuntime {
  private params: RoleAssignmentParams
  private game!: Game
  /** role_id → set of entity_ids currently holding it. */
  private assignments = new Map<string, Set<string>>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as RoleAssignmentParams
  }

  init(game: Game): void {
    this.game = game
    for (const role of this.params.roles) this.assignments.set(role, new Set())
    for (const [role, entity] of Object.entries(this.params.initial_assignments ?? {})) {
      this.assign(role, entity)
    }
  }

  update(_dt: number): void { /* state-only mechanic */ }

  dispose(): void { this.assignments.clear() }

  expose(): Record<string, unknown> {
    const flat: Record<string, string[]> = {}
    for (const [role, ents] of this.assignments) flat[role] = [...ents]
    return {
      role_assignments: flat,
      role_count: this.assignments.size,
      allow_multi_role: !!this.params.allow_multi_role,
    }
  }

  // ---- Public API ----

  /** Assign a role to an entity. Returns false if the role isn't
   *  declared. When `allow_multi_role=false` and the role already has
   *  a holder, the prior holder is stripped. */
  assign(role: string, entity: string): boolean {
    if (!this.assignments.has(role)) return false
    const tag = this.params.assignable_tag
    if (tag && !this.entityHasTag(entity, tag)) return false

    const set = this.assignments.get(role)!
    if (!this.params.allow_multi_role && set.size > 0 && !set.has(entity)) {
      set.clear()  // single-holder role — steal from prior holder
    }
    set.add(entity)
    try { writeWorldFlag(this.game, `role.${role}`, entity) } catch { /* ignore */ }
    return true
  }

  /** Revoke a role from a specific entity (or all holders if `entity`
   *  omitted). Returns true if something was revoked. */
  revoke(role: string, entity?: string): boolean {
    const set = this.assignments.get(role)
    if (!set || set.size === 0) return false
    if (entity === undefined) {
      set.clear()
      try { writeWorldFlag(this.game, `role.${role}`, null) } catch { /* ignore */ }
      return true
    }
    const deleted = set.delete(entity)
    if (deleted) {
      try { writeWorldFlag(this.game, `role.${role}`, set.size > 0 ? [...set][0] : null) } catch { /* ignore */ }
    }
    return deleted
  }

  /** Swap the holder of a single-holder role to a new entity. Returns
   *  the prior holder's id (or null if the role was empty). */
  swap(role: string, newEntity: string): string | null {
    const set = this.assignments.get(role)
    if (!set) return null
    const prior = set.size > 0 ? [...set][0] : null
    if (!this.assign(role, newEntity)) return null
    return prior !== newEntity ? prior : null
  }

  /** Return every entity currently holding `role`. */
  holdersOf(role: string): string[] {
    return [...(this.assignments.get(role) ?? new Set())]
  }

  /** Return every role currently held by `entity`. */
  rolesHeldBy(entity: string): string[] {
    const out: string[] = []
    for (const [role, ents] of this.assignments) {
      if (ents.has(entity)) out.push(role)
    }
    return out
  }

  hasRole(role: string): boolean { return this.assignments.has(role) }
  listRoles(): string[] { return [...this.assignments.keys()] }

  // ---- Internals ----

  private entityHasTag(entity: string, tag: string): boolean {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>>) ?? []
    for (const e of entities) {
      if ((e as { id?: string }).id !== entity) continue
      const tags = (e.tags as string[] | undefined) ?? []
      return tags.includes(tag)
    }
    return false
  }
}

mechanicRegistry.register('RoleAssignment', (instance, game) => {
  const rt = new RoleAssignmentRuntime(instance)
  rt.init(game)
  return rt
})
