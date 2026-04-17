// StatusStack — Phase 4 extension mechanic.
//
// RPG-style status effects. Each status has tags, duration, optional tick
// effect, on_apply / on_expire actions, and max_stacks cap. Conflict rules
// resolve overlapping statuses (remove_present / block_apply / both_remain).

import type { Game } from '../../game/game'
import type { ActionRef, MechanicInstance, StatusStackParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

type StatusSpec = StatusStackParams['statuses'][number]
type ConflictRule = NonNullable<StatusStackParams['conflict_rules']>[number]

interface ActiveStatus {
  name: string
  remainingSec: number | null    // null = indefinite
  spec: StatusSpec
}

class StatusStackRuntime implements MechanicRuntime {
  private params: StatusStackParams
  private game!: Game
  private perEntity = new Map<string, ActiveStatus[]>()
  private specByName = new Map<string, StatusSpec>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as StatusStackParams
    for (const s of this.params.statuses ?? []) this.specByName.set(s.name, s)
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    for (const [, list] of this.perEntity) {
      for (let i = list.length - 1; i >= 0; i--) {
        const st = list[i]
        if (st.remainingSec !== null) {
          st.remainingSec -= dt
          if (st.remainingSec <= 0) {
            if (st.spec.on_expire) this.fire(st.spec.on_expire)
            list.splice(i, 1)
            continue
          }
        }
        if (st.spec.tick_effect) this.fire(st.spec.tick_effect)
      }
    }
  }

  dispose(): void { this.perEntity.clear() }

  /** External: apply `statusName` to `entity`. Returns true if applied. */
  apply(statusName: string, entity: Record<string, unknown>): boolean {
    const spec = this.specByName.get(statusName)
    if (!spec) return false
    const id = this.entityId(entity)
    let list = this.perEntity.get(id)
    if (!list) { list = []; this.perEntity.set(id, list) }
    // Conflict-rule resolution.
    for (const rule of this.params.conflict_rules ?? []) {
      if (rule.and_applying === statusName && list.some(s => s.name === rule.if_present)) {
        if (rule.resolve === 'block_apply') return false
        if (rule.resolve === 'remove_present') {
          for (let i = list.length - 1; i >= 0; i--) {
            if (list[i].name === rule.if_present) list.splice(i, 1)
          }
        }
        // both_remain → fall through
      }
    }
    // Stack cap: at max_stacks, refresh the oldest instead of adding.
    const max = spec.max_stacks ?? 1
    const existing = list.filter(s => s.name === statusName)
    if (existing.length >= max) {
      existing[0].remainingSec = spec.duration_sec ?? null
      return true
    }
    list.push({ name: statusName, spec, remainingSec: spec.duration_sec ?? null })
    if (spec.on_apply) this.fire(spec.on_apply)
    return true
  }

  expose(): Record<string, unknown> {
    const summary: Record<string, Array<{ name: string; remaining: number | null }>> = {}
    for (const [id, list] of this.perEntity) {
      summary[id] = list.map(s => ({ name: s.name, remaining: s.remainingSec }))
    }
    return { active: summary }
  }

  private entityId(entity: Record<string, unknown>): string {
    return String(entity.name ?? JSON.stringify(entity.position))
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

// Unused-helper hush-up so strict TS compiles when conflict_rules is
// optional and never touched by the type-checker at this scope.
const _conflictRuleShape: ConflictRule = { if_present: '', and_applying: '', resolve: 'both_remain' }
void _conflictRuleShape

mechanicRegistry.register('StatusStack', (instance, game) => {
  const rt = new StatusStackRuntime(instance)
  rt.init(game)
  return rt
})
