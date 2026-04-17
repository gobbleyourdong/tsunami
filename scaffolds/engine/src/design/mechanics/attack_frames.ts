// AttackFrames — Phase 4 extension mechanic.
//
// Fighter-game frame data: per-attack states with explicit startup, active,
// and recovery windows. Each state defines hitbox + hurtbox_override. The
// mechanic tracks the active frame state per archetype instance and surfaces
// per-frame active/invulnerable windows via expose().
//
// v1 integrates at the property level: setting entity.properties.attack_state
// drives which state the archetype is in, and the mechanic advances through
// startup → active → recovery on each update tick. External callers trigger
// an attack via beginAttack(stateName).

import type { Game } from '../../game/game'
import type { AttackFramesParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

type AttackState = AttackFramesParams['states'][number]

interface ActiveAttack {
  entity: Record<string, unknown>
  state: AttackState
  phase: 'startup' | 'active' | 'recovery'
  elapsedMs: number
}

class AttackFramesRuntime implements MechanicRuntime {
  private params: AttackFramesParams
  private game!: Game
  private active: ActiveAttack[] = []
  private stateByName = new Map<string, AttackState>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as AttackFramesParams
    for (const s of this.params.states ?? []) this.stateByName.set(s.name, s)
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    const dtMs = dt * 1000
    for (let i = this.active.length - 1; i >= 0; i--) {
      const a = this.active[i]
      a.elapsedMs += dtMs
      const { state } = a
      if (a.phase === 'startup' && a.elapsedMs >= state.startup_ms) {
        a.phase = 'active'
        a.elapsedMs = 0
        this.stampPhase(a)
      } else if (a.phase === 'active' && a.elapsedMs >= state.active_ms) {
        a.phase = 'recovery'
        a.elapsedMs = 0
        this.stampPhase(a)
      } else if (a.phase === 'recovery' && a.elapsedMs >= state.recovery_ms) {
        this.clearPhase(a.entity)
        this.active.splice(i, 1)
      }
    }
  }

  dispose(): void {
    for (const a of this.active) this.clearPhase(a.entity)
    this.active = []
  }

  /** External: begin `stateName` attack for the first matching archetype
   *  instance. Returns true if the attack was queued. */
  beginAttack(stateName: string, entity?: Record<string, unknown>): boolean {
    const state = this.stateByName.get(stateName)
    if (!state) return false
    const e = entity ?? this.findEntity()
    if (!e) return false
    // Disallow overlapping attacks on the same entity.
    if (this.active.some(a => a.entity === e)) return false
    this.active.push({ entity: e, state, phase: 'startup', elapsedMs: 0 })
    this.stampPhase(this.active[this.active.length - 1])
    return true
  }

  expose(): Record<string, unknown> {
    return {
      activeAttacks: this.active.map(a => ({
        state: a.state.name, phase: a.phase, elapsedMs: a.elapsedMs,
      })),
      registeredStates: [...this.stateByName.keys()],
    }
  }

  private findEntity(): Record<string, unknown> | null {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    return entities.find(e => e.type === aid) ?? null
  }

  private stampPhase(a: ActiveAttack): void {
    const props = (a.entity.properties ?? {}) as Record<string, unknown>
    props.attack_state = a.state.name
    props.attack_phase = a.phase
    if (a.phase === 'active' && a.state.hitbox) props.hitbox = a.state.hitbox
    else delete props.hitbox
    if (a.state.hurtbox_override) props.hurtbox = a.state.hurtbox_override
    a.entity.properties = props
  }

  private clearPhase(entity: Record<string, unknown>): void {
    const props = (entity.properties ?? {}) as Record<string, unknown>
    delete props.attack_state
    delete props.attack_phase
    delete props.hitbox
    entity.properties = props
  }
}

mechanicRegistry.register('AttackFrames', (instance, game) => {
  const rt = new AttackFramesRuntime(instance)
  rt.init(game)
  return rt
})
