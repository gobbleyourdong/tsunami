// VisionCone — Phase 4 extension mechanic.
//
// Stealth-game awareness state machine. Watcher archetype has a
// cone_angle_deg / cone_range vision cone. When a target-tagged entity
// enters the cone (optionally with line_of_sight gate), the watcher
// transitions through alert_states. Each state has optional decay_to /
// decay_sec / on_enter action / ai_override that replaces the archetype's
// base AI while active.

import type { Game } from '../../game/game'
import type { ActionRef, MechanicInstance, VisionConeParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

type AlertState = VisionConeParams['alert_states'][number]

interface WatcherState {
  entity: Record<string, unknown>
  state: string
  secInState: number
}

class VisionConeRuntime implements MechanicRuntime {
  private params: VisionConeParams
  private game!: Game
  private watchers = new Map<string, WatcherState>()
  private stateByName = new Map<string, AlertState>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as VisionConeParams
    for (const s of this.params.alert_states ?? []) this.stateByName.set(s.name, s)
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    const targets = entities.filter(e => {
      const tags = (((e.properties as Record<string, unknown> | undefined)?.tags) ?? []) as string[]
      return Array.isArray(tags) && this.params.target_tags.some(t => tags.includes(t))
    })
    for (const w of entities) {
      if (w.type !== aid) continue
      const id = this.entityId(w)
      let ws = this.watchers.get(id)
      if (!ws) {
        ws = { entity: w, state: this.params.initial_state, secInState: 0 }
        this.watchers.set(id, ws)
        this.enterState(ws, ws.state)
      }
      ws.secInState += dt
      const seesTarget = this.anyTargetInCone(w, targets)
      if (seesTarget) {
        // Escalate: move to 'alert' if not already there.
        if (ws.state !== 'alert' && this.stateByName.has('alert')) {
          this.transitionTo(ws, 'alert')
        }
      } else {
        // Decay per state rules.
        const spec = this.stateByName.get(ws.state)
        if (spec?.decay_to && spec.decay_sec && ws.secInState >= spec.decay_sec) {
          this.transitionTo(ws, spec.decay_to)
        }
      }
    }
  }

  dispose(): void { this.watchers.clear() }

  expose(): Record<string, unknown> {
    return {
      watchers: [...this.watchers.values()].map(w => ({
        state: w.state, secInState: w.secInState,
      })),
    }
  }

  private enterState(w: WatcherState, name: string): void {
    const spec = this.stateByName.get(name)
    if (!spec) return
    w.state = name
    w.secInState = 0
    if (spec.ai_override) {
      const props = (w.entity.properties ?? {}) as Record<string, unknown>
      props.ai = spec.ai_override
      w.entity.properties = props
    }
    if (spec.on_enter) this.fire(spec.on_enter)
  }

  private transitionTo(w: WatcherState, name: string): void {
    if (w.state === name) return
    this.enterState(w, name)
  }

  private anyTargetInCone(
    watcher: Record<string, unknown>,
    targets: Array<Record<string, unknown>>,
  ): boolean {
    const wp = (watcher.position as [number, number, number] | undefined) ?? [0, 0, 0]
    const wprops = (watcher.properties as Record<string, unknown> | undefined) ?? {}
    const wrot = (wprops.facing as [number, number, number] | undefined) ?? [0, 0, 1]
    const halfAngle = (this.params.cone_angle_deg ?? 60) * Math.PI / 360
    const range = this.params.cone_range ?? 10
    for (const t of targets) {
      const tp = (t.position as [number, number, number] | undefined) ?? [0, 0, 0]
      const dx = tp[0] - wp[0], dz = tp[2] - wp[2]
      const dist2 = dx * dx + dz * dz
      if (dist2 > range * range) continue
      const dist = Math.sqrt(dist2) || 1
      const dotp = (dx / dist) * wrot[0] + (dz / dist) * wrot[2]
      const angleCos = Math.cos(halfAngle)
      if (dotp >= angleCos) return true
    }
    return false
  }

  private entityId(e: Record<string, unknown>): string {
    return String(e.name ?? JSON.stringify(e.position))
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

mechanicRegistry.register('VisionCone', (instance, game) => {
  const rt = new VisionConeRuntime(instance)
  rt.init(game)
  return rt
})
