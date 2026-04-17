// LevelSequence — Phase 3 action-core mechanic.
//
// Owns the flow between discrete levels. Tracks current level id,
// advances on win_condition, retries / goes back / fails out based on
// each level's on_win / on_fail directives. cycle_on_complete loops back
// to start_at after the final level completes.
//
// The compiler lowers this mechanic's levels into individual scenes
// named `<flow_scene_name>.<level_id>`. Runtime side: flag
// `next_level_requested` / `previous_level_requested` / `retry_level_requested`
// so the flow machine can observe and transition.

import type { Game } from '../../game/game'
import type { LevelSequenceParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy, writeWorldFlag } from './world_flags'

class LevelSequenceRuntime implements MechanicRuntime {
  private params: LevelSequenceParams
  private game!: Game
  private currentIndex: number
  private levelCompleted = false

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as LevelSequenceParams
    this.currentIndex = Math.max(0,
      (this.params.levels ?? []).findIndex(l => l.id === this.params.start_at))
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    const level = this.params.levels?.[this.currentIndex]
    if (!level) return
    if (this.levelCompleted) return

    if (level.win_condition && flagTruthy(this.game, level.win_condition as unknown as string)) {
      this.levelCompleted = true
      this.handleWin()
      return
    }
    if (level.fail_condition && flagTruthy(this.game, level.fail_condition as unknown as string)) {
      this.levelCompleted = true
      this.handleFail()
    }
  }

  dispose(): void { /* state is per-scene; nothing to release */ }

  expose(): Record<string, unknown> {
    const level = this.params.levels?.[this.currentIndex]
    return {
      currentLevelId: level?.id ?? null,
      currentIndex: this.currentIndex,
      totalLevels: this.params.levels?.length ?? 0,
      levelCompleted: this.levelCompleted,
    }
  }

  private handleWin(): void {
    const level = this.params.levels?.[this.currentIndex]
    const next = level?.on_win ?? 'next'
    if (next === 'next') {
      this.advanceIndex(+1)
    } else if (typeof next === 'string') {
      // Explicit level id — find and jump.
      const idx = (this.params.levels ?? []).findIndex(l => l.id === next)
      if (idx >= 0) this.setIndex(idx)
    }
  }

  private handleFail(): void {
    const level = this.params.levels?.[this.currentIndex]
    const fail = level?.on_fail ?? 'retry'
    if (fail === 'retry') {
      writeWorldFlag(this.game, 'retry_level_requested', true)
      this.levelCompleted = false
    } else if (fail === 'previous') {
      this.advanceIndex(-1)
    } else if (typeof fail === 'string') {
      const idx = (this.params.levels ?? []).findIndex(l => l.id === fail)
      if (idx >= 0) this.setIndex(idx)
    }
  }

  private advanceIndex(delta: number): void {
    const total = this.params.levels?.length ?? 0
    let next = this.currentIndex + delta
    if (next >= total) {
      if (this.params.cycle_on_complete) next = 0
      else return  // stay put; flow handles game-complete separately
    }
    if (next < 0) next = 0
    this.setIndex(next)
  }

  private setIndex(idx: number): void {
    this.currentIndex = idx
    this.levelCompleted = false
    writeWorldFlag(this.game, 'next_level_requested', true)
  }
}

mechanicRegistry.register('LevelSequence', (instance, game) => {
  const rt = new LevelSequenceRuntime(instance)
  rt.init(game)
  return rt
})
