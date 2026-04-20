// PhysicsModifier — v1.3 physics extension (Cycle 16).
//
// Global physics scale. Modifies gravity / friction / time-scale for
// the whole scene, or (when `affects_tag` is set) only entities
// carrying that tag. The mechanic exposes its scales via expose() so
// physics systems can read them each frame.
//
// Use cases:
//   - Platformer scaffold tunes gravity_scale for jump feel
//   - VVVVVV-style games set gravity_scale = -1 to flip gravity
//   - Superhot sets time_scale = 0.1 when player stands still
//   - Chrono Trigger's Haste could set time_scale > 1 scene-scoped

import type { Game } from '../../game/game'
import type { PhysicsModifierParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

class PhysicsModifierRuntime implements MechanicRuntime {
  private params: PhysicsModifierParams
  private game!: Game
  private gravityScale: number
  private frictionScale: number
  private timeScale: number
  private affectsTag?: string

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as PhysicsModifierParams
    this.gravityScale = this.params.gravity_scale
    this.frictionScale = this.params.friction_scale
    this.timeScale = this.params.time_scale
    this.affectsTag = this.params.affects_tag
  }

  init(game: Game): void {
    this.game = game
    this.publish()
  }

  update(_dt: number): void { /* state-only mechanic — physics systems read via expose() */ }

  dispose(): void {
    // Restore defaults on dispose so the next scene starts clean.
    this.gravityScale = 1.0
    this.frictionScale = 1.0
    this.timeScale = 1.0
    this.publish()
  }

  expose(): Record<string, unknown> {
    return {
      gravity_scale: this.gravityScale,
      friction_scale: this.frictionScale,
      time_scale: this.timeScale,
      affects_tag: this.affectsTag ?? null,
    }
  }

  // ---- Public API ----

  /** Runtime tuning — e.g. jump code calls setGravityScale(0.5) while
   *  rising for a snappier arc, then reverts at apex. */
  setGravityScale(v: number): void {
    this.gravityScale = v
    this.publish('gravity_scale', v)
  }

  setFrictionScale(v: number): void {
    this.frictionScale = v
    this.publish('friction_scale', v)
  }

  setTimeScale(v: number): void {
    // Clamp to a sane range — negative time_scale is better expressed via
    // a dedicated TimeReverseMechanic (v2 placeholder), not here.
    this.timeScale = Math.max(0, v)
    this.publish('time_scale', this.timeScale)
  }

  /** Convenience — one call sets all three. */
  setAll(gravity: number, friction: number, time: number): void {
    this.gravityScale = gravity
    this.frictionScale = friction
    this.timeScale = Math.max(0, time)
    this.publish()
  }

  /** Read API — physics systems call this each frame. */
  getGravityScale(): number { return this.gravityScale }
  getFrictionScale(): number { return this.frictionScale }
  getTimeScale(): number { return this.timeScale }
  getAffectsTag(): string | undefined { return this.affectsTag }

  private publish(key?: string, value?: number): void {
    try {
      if (key && value !== undefined) {
        writeWorldFlag(this.game, `physics.${key}`, value)
      } else {
        writeWorldFlag(this.game, 'physics.gravity_scale', this.gravityScale)
        writeWorldFlag(this.game, 'physics.friction_scale', this.frictionScale)
        writeWorldFlag(this.game, 'physics.time_scale', this.timeScale)
      }
    } catch { /* world_flags may not be available in all scenes */ }
  }
}

mechanicRegistry.register('PhysicsModifier', (instance, game) => {
  const rt = new PhysicsModifierRuntime(instance)
  rt.init(game)
  return rt
})
