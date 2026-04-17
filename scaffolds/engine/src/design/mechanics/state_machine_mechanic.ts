// StateMachineMechanic — Phase 4 extension mechanic.
//
// General per-archetype finite state machine. Named states each have
// optional enter/exit actions. Transitions fire on condition-DSL expression
// matches against world_flags + entity properties. Initial state is applied
// at init. External callers can force transitions via forceState(name).

import type { Game } from '../../game/game'
import type { ActionRef, MechanicInstance, StateMachineMechanicParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy } from './world_flags'

class StateMachineMechanicRuntime implements MechanicRuntime {
  private params: StateMachineMechanicParams
  private game!: Game
  private currentState: string
  private stateByName = new Map<string, StateMachineMechanicParams['states'][number]>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as StateMachineMechanicParams
    this.currentState = this.params.initial
    for (const s of this.params.states ?? []) this.stateByName.set(s.name, s)
  }

  init(game: Game): void {
    this.game = game
    const s = this.stateByName.get(this.currentState)
    if (s?.enter) this.fire(s.enter)
  }

  update(_dt: number): void {
    for (const t of this.params.transitions ?? []) {
      if (t.from !== this.currentState) continue
      if (this.conditionMet(t.when)) {
        this.forceState(t.to)
        return
      }
    }
  }

  dispose(): void { /* no timers */ }

  forceState(name: string): void {
    const next = this.stateByName.get(name)
    if (!next) return
    const prev = this.stateByName.get(this.currentState)
    if (prev?.exit) this.fire(prev.exit)
    this.currentState = name
    if (next.enter) this.fire(next.enter)
    this.stamp()
  }

  expose(): Record<string, unknown> {
    return {
      currentState: this.currentState,
      states: [...this.stateByName.keys()],
    }
  }

  /** Minimal condition DSL v1:
   *  - bare ident → truthy world_flag
   *  - "flag == value" | "flag != value" → equality
   *  - "score >= 100" | "score < 10" → numeric compare
   *  Full DSL TODO via the Ether pass (per schema comment). */
  private conditionMet(when: string): boolean {
    if (!when) return false
    const trimmed = when.trim()
    const ops = [">=", "<=", "==", "!=", ">", "<", "="]
    for (const op of ops) {
      const i = trimmed.indexOf(op)
      if (i < 0) continue
      const lhs = trimmed.slice(0, i).trim()
      const rhs = trimmed.slice(i + op.length).trim().replace(/^['"]|['"]$/g, "")
      const lval = this.readVar(lhs)
      const rvalNum = Number(rhs)
      const rvalBool = rhs === 'true' ? true : rhs === 'false' ? false : undefined
      const rcmp: unknown = !Number.isNaN(rvalNum) ? rvalNum : (rvalBool ?? rhs)
      switch (op) {
        case "==": case "=": return lval === rcmp
        case "!=": return lval !== rcmp
        case ">=": return typeof lval === 'number' && typeof rcmp === 'number' && lval >= rcmp
        case "<=": return typeof lval === 'number' && typeof rcmp === 'number' && lval <= rcmp
        case ">":  return typeof lval === 'number' && typeof rcmp === 'number' && lval > rcmp
        case "<":  return typeof lval === 'number' && typeof rcmp === 'number' && lval < rcmp
      }
    }
    return flagTruthy(this.game, trimmed)
  }

  private readVar(name: string): unknown {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const props = active?.properties as Record<string, unknown> | undefined
    const flags = (props?.world_flags ?? {}) as Record<string, unknown>
    if (name in flags) return flags[name]
    // Fallback: read from archetype entity property of the same name
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    for (const e of entities) {
      if (e.type !== aid) continue
      const ep = (e.properties as Record<string, unknown> | undefined) ?? {}
      if (name in ep) return ep[name]
    }
    return undefined
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }

  private stamp(): void {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    for (const e of entities) {
      if (e.type !== aid) continue
      const p = (e.properties ?? {}) as Record<string, unknown>
      p.sm_state = this.currentState
      e.properties = p
    }
  }
}

mechanicRegistry.register('StateMachineMechanic', (instance, game) => {
  const rt = new StateMachineMechanicRuntime(instance)
  rt.init(game)
  return rt
})
