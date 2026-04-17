// PuzzleObject — Phase 1 content-multiplier mechanic.
//
// State-graph attached to a target archetype. States have an optional
// mesh/tint override + on_enter action. Transitions fire on interactions
// (examine / use / touch), item-used events, world-flag changes, or
// adjacent-state conditions. Fires an effect ActionRef on successful
// transition.
//
// v1 integrates at the entity-properties level: when a state changes we
// mutate the entity's `properties.state`, `properties.mesh`, and
// `properties.tint` directly so the renderer picks up the change on its
// next draw. External code triggers transitions by calling
// `handleInteraction(kind)` or `notifyItemUsed(item)` on the runtime.

import type { Game } from '../../game/game'
import type {
  ActionRef,
  MechanicInstance,
  PuzzleObjectParams,
} from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

type Transition = PuzzleObjectParams['transitions'][number]
type State = PuzzleObjectParams['states'][number]

class PuzzleObjectRuntime implements MechanicRuntime {
  private params: PuzzleObjectParams
  private game!: Game
  private currentState: string
  private stateByName = new Map<string, State>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as PuzzleObjectParams
    this.currentState = this.params.initial_state
    for (const s of this.params.states ?? []) this.stateByName.set(s.name, s)
  }

  init(game: Game): void {
    this.game = game
    this.applyStateToEntities(this.currentState)
  }

  update(_dt: number): void {
    // Passive for v1 — check adjacent-state conditions each frame so
    // cascading state transitions resolve without polling pressure on
    // the author. Sample size small (most puzzles < 10 objects) so O(N²)
    // pass is cheap.
    for (const t of this.params.transitions ?? []) {
      if (t.from !== this.currentState) continue
      if (this.triggerMatches(t, 'passive')) this.transitionTo(t)
    }
  }

  dispose(): void { /* no timers to clear */ }

  /** External call: player examined / used / touched one of the entities. */
  handleInteraction(kind: 'examine' | 'use' | 'touch'): void {
    for (const t of this.params.transitions ?? []) {
      if (t.from !== this.currentState) continue
      const tb = t.triggered_by as Record<string, unknown>
      if ((tb.interaction as string | undefined) === kind) {
        this.transitionTo(t)
        return
      }
    }
  }

  /** External call: player used an item whose name matches a transition trigger. */
  notifyItemUsed(item: string): void {
    for (const t of this.params.transitions ?? []) {
      if (t.from !== this.currentState) continue
      const tb = t.triggered_by as Record<string, unknown>
      if ((tb.item_used as string | undefined) === item) {
        this.transitionTo(t)
        return
      }
    }
  }

  expose(): Record<string, unknown> {
    return {
      currentState: this.currentState,
      states: [...this.stateByName.keys()],
      transitionsAvailable: (this.params.transitions ?? [])
        .filter(t => t.from === this.currentState)
        .map(t => ({ to: t.to, kind: kindOf(t) })),
    }
  }

  // ───────── private ─────────

  private transitionTo(t: Transition): void {
    const target = this.stateByName.get(t.to)
    if (!target) return
    this.currentState = t.to
    this.applyStateToEntities(t.to)
    if (target.on_enter) this.fire(target.on_enter)
    if (t.effect) this.fire(t.effect)
  }

  private applyStateToEntities(stateName: string): void {
    const state = this.stateByName.get(stateName)
    if (!state) return
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    for (const e of entities) {
      if (e.type !== this.params.archetype as unknown as string) continue
      const props = (e.properties ?? {}) as Record<string, unknown>
      props.state = stateName
      if (state.mesh) props.mesh = state.mesh
      if (state.tint) props.tint = state.tint
      e.properties = props
    }
  }

  private triggerMatches(t: Transition, ctx: 'passive' | 'examine' | 'use' | 'touch'): boolean {
    const tb = t.triggered_by as Record<string, unknown>
    if (tb.world_flag && ctx === 'passive') {
      return this.readWorldFlag(tb.world_flag as string) === (tb.value ?? true)
    }
    if (tb.adjacent_state && ctx === 'passive') {
      const adj = tb.adjacent_state as { archetype: string; state: string }
      return this.anyAdjacentInState(adj.archetype, adj.state)
    }
    return false
  }

  private readWorldFlag(key: string): unknown {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const props = (active?.properties ?? {}) as Record<string, unknown>
    const flags = (props.world_flags ?? {}) as Record<string, unknown>
    return flags[key]
  }

  private anyAdjacentInState(archetype: string, state: string): boolean {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    return entities.some(e => {
      if (e.type !== archetype) return false
      const props = (e.properties ?? {}) as Record<string, unknown>
      return props.state === state
    })
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

function kindOf(t: Transition): string {
  const tb = t.triggered_by as Record<string, unknown>
  if (tb.interaction) return `interaction:${tb.interaction}`
  if (tb.item_used) return `item_used:${tb.item_used}`
  if (tb.world_flag) return `world_flag:${tb.world_flag}`
  if (tb.adjacent_state) return 'adjacent_state'
  return 'unknown'
}

mechanicRegistry.register('PuzzleObject', (instance, game) => {
  const rt = new PuzzleObjectRuntime(instance)
  rt.init(game)
  return rt
})
