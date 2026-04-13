/**
 * Finite State Machine — generic, typed states with enter/exit/update hooks.
 */

export interface FSMState<TContext = unknown> {
  name: string
  onEnter?: (ctx: TContext) => void
  onExit?: (ctx: TContext) => void
  onUpdate?: (ctx: TContext, dt: number) => void
}

export interface FSMTransition<TContext = unknown> {
  from: string
  to: string
  condition: (ctx: TContext) => boolean
  priority?: number
}

export class FiniteStateMachine<TContext = unknown> {
  private states = new Map<string, FSMState<TContext>>()
  private transitions: FSMTransition<TContext>[] = []
  private currentStateName = ''
  private context: TContext

  onStateChange?: (from: string, to: string) => void

  constructor(context: TContext) {
    this.context = context
  }

  addState(state: FSMState<TContext>): this {
    this.states.set(state.name, state)
    if (!this.currentStateName) this.currentStateName = state.name
    return this
  }

  addTransition(from: string, to: string, condition: (ctx: TContext) => boolean, priority = 0): this {
    this.transitions.push({ from, to, condition, priority })
    return this
  }

  /** Force-set the current state (calls exit/enter). */
  setState(name: string): void {
    const prev = this.states.get(this.currentStateName)
    const next = this.states.get(name)
    if (!next) return
    prev?.onExit?.(this.context)
    const from = this.currentStateName
    this.currentStateName = name
    next.onEnter?.(this.context)
    this.onStateChange?.(from, name)
  }

  get current(): string {
    return this.currentStateName
  }

  update(dt: number): void {
    // Check transitions (highest priority first)
    const candidates = this.transitions
      .filter(t => t.from === this.currentStateName || t.from === '*')
      .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))

    for (const t of candidates) {
      if (t.condition(this.context)) {
        this.setState(t.to)
        break
      }
    }

    // Update current state
    const state = this.states.get(this.currentStateName)
    state?.onUpdate?.(this.context, dt)
  }

  /** Serialize current state name. */
  serialize(): string {
    return this.currentStateName
  }

  /** Restore from serialized state. */
  deserialize(stateName: string): void {
    if (this.states.has(stateName)) {
      this.currentStateName = stateName
    }
  }
}
