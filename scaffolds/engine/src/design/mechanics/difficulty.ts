// Difficulty — Phase 3 action-core mechanic.
//
// S-curve ramp over a drive signal (time | score | wave_index | level |
// custom). Publishes named multipliers via expose() that other mechanics
// (WaveSpawner, BulletPattern, enemy stats) read on their tick.
//
// Interpolation: sigmoid from easy to hard as drive / max_level → 1.0.
// Below 0 locks to easy, above 1 locks to hard. Linear smoothstep keeps
// the curve controllable without tuning exponents.

import type { Game } from '../../game/game'
import type { DifficultyParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class DifficultyRuntime implements MechanicRuntime {
  private params: DifficultyParams
  private game!: Game
  private level = 0
  private elapsedSec = 0
  private multipliers: Record<string, number> = {}

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as DifficultyParams
    this.computeMultipliers(0)
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    this.elapsedSec += dt
    const t = this.driveSignal()
    this.level = Math.min(this.params.max_level, Math.max(0, Math.round(t * this.params.max_level)))
    this.computeMultipliers(t)
  }

  dispose(): void { /* no state to tear down */ }

  expose(): Record<string, unknown> {
    return { level: this.level, ...this.multipliers }
  }

  private driveSignal(): number {
    switch (this.params.drive) {
      case 'time':       return Math.min(1, this.elapsedSec / 300)  // 5-min ramp default
      case 'wave_index': return Math.min(1, this.level / this.params.max_level)
      case 'score':      return this.readField('Score')
      case 'level':      return Math.min(1, this.level / this.params.max_level)
      case 'custom':     return 0
    }
    return 0
  }

  private readField(name: string): number {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    // First entity carrying the named component provides the value.
    for (const e of entities) {
      const props = e.properties as Record<string, unknown> | undefined
      const v = props?.[name]
      if (typeof v === 'number') return Math.min(1, v / 10_000)
    }
    return 0
  }

  private computeMultipliers(t: number): void {
    // Smoothstep blend: 3t² − 2t³ keeps endpoints pinned.
    const s = Math.max(0, Math.min(1, 3 * t * t - 2 * t * t * t))
    const easy = this.params.easy ?? {}
    const hard = this.params.hard ?? {}
    const keys = new Set([...Object.keys(easy), ...Object.keys(hard)])
    for (const k of keys) {
      const e = easy[k] ?? 1
      const h = hard[k] ?? e
      this.multipliers[k] = e + (h - e) * s
    }
  }
}

mechanicRegistry.register('Difficulty', (instance, game) => {
  const rt = new DifficultyRuntime(instance)
  rt.init(game)
  return rt
})
