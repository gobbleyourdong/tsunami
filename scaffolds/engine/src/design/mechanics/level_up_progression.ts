// LevelUpProgression — Phase 3 JRPG mechanic (v1.2).
//
// XP → level curve with flat stat-deltas applied on each level-up.
// Optionally grants a spell / ability when specific levels are reached.
//
// Universal in RPG genres (JRPG / CRPG / ARPG) and common in action-
// adventure, roguelike, and metroidvania power-ups. Per JOB-A corpus
// census (GENRE_MECHANIC_MATRIX.md): genuine-universal, keyword
// false-positive-heavy.
//
// XP is fed via grantXP(target, amount) — called by combat mechanics
// (TurnBasedCombat / ATBCombat / AttackFrames) when enemies drop or
// actions resolve. The mechanic walks active party members and
// checks threshold crossing each update.

import type { Game } from '../../game/game'
import type { LevelUpProgressionParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

// Per-entity runtime state (separate from the mechanic params so the
// same LevelUpProgression instance can serve a whole party).
interface EntityProgress {
  level: number
  xp: number
  xp_to_next: number
}

class LevelUpProgressionRuntime implements MechanicRuntime {
  private params: LevelUpProgressionParams
  private game!: Game
  private progress = new Map<string, EntityProgress>()
  private pendingLevelUps: Array<{ target: string; new_level: number }> = []

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as LevelUpProgressionParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    // Apply pending level-ups (deferred so the granting frame settles).
    while (this.pendingLevelUps.length > 0) {
      const { target, new_level } = this.pendingLevelUps.shift()!
      this.applyLevelUp(target, new_level)
    }
  }

  dispose(): void {
    this.progress.clear()
    this.pendingLevelUps.length = 0
  }

  expose(): Record<string, unknown> {
    const snapshot: Record<string, unknown> = {}
    for (const [id, p] of this.progress) {
      snapshot[`${id}.level`] = p.level
      snapshot[`${id}.xp`] = p.xp
      snapshot[`${id}.xp_to_next`] = p.xp_to_next
    }
    return snapshot
  }

  /** Public API — combat mechanics call this to award XP to a target. */
  grantXP(target: string, amount: number): void {
    const entry = this.getOrInit(target)
    entry.xp += amount
    while (entry.xp >= entry.xp_to_next && entry.level < this.params.max_level) {
      entry.xp -= entry.xp_to_next
      entry.level += 1
      entry.xp_to_next = this.xpForLevel(entry.level + 1)
      this.pendingLevelUps.push({ target, new_level: entry.level })
    }
    if (entry.level >= this.params.max_level) {
      entry.xp = 0
      entry.xp_to_next = 0
    }
  }

  /** Read current progress for a target — used by HUD / save system. */
  getProgress(target: string): EntityProgress | undefined {
    return this.progress.get(target)
  }

  private getOrInit(target: string): EntityProgress {
    let p = this.progress.get(target)
    if (!p) {
      p = { level: 1, xp: 0, xp_to_next: this.xpForLevel(2) }
      this.progress.set(target, p)
    }
    return p
  }

  private xpForLevel(level: number): number {
    // XP needed to GO from (level-1) to `level`, relative to the base.
    // Curves:
    //   linear      → base * level
    //   quadratic   → base * level²
    //   exponential → base * 2^(level-1)
    //   custom      → fallback to linear (caller should override)
    if (level <= 1) return 0
    const l = level - 1  // level 2 needs `base * 1` under linear
    switch (this.params.xp_curve) {
      case 'linear':      return Math.round(this.params.base_xp * l)
      case 'quadratic':   return Math.round(this.params.base_xp * l * l)
      case 'exponential': return Math.round(this.params.base_xp * Math.pow(2, l - 1))
      case 'custom':      return Math.round(this.params.base_xp * l)
    }
    return Math.round(this.params.base_xp * l)
  }

  private applyLevelUp(target: string, new_level: number): void {
    // Find the entity in the active scene and mutate its Stats / Level
    // components. If no entity found, we still emit the condition —
    // an HUD or cutscene system may want the signal regardless.
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    for (const e of entities) {
      if ((e as { id?: string }).id !== target) continue
      const props = (e.properties ?? {}) as Record<string, Record<string, unknown>>

      // Update Level component if present (otherwise create it).
      const levelComp = (props.Level ??= { current: 1, xp: 0 }) as Record<string, number>
      levelComp.current = new_level
      levelComp.xp = this.progress.get(target)?.xp ?? 0
      levelComp.xp_to_next = this.progress.get(target)?.xp_to_next ?? 0

      // Apply stat deltas to Stats component (if present).
      const stats = (props.Stats ??= {}) as Record<string, number>
      for (const [stat, delta] of Object.entries(this.params.stat_gains ?? {})) {
        stats[stat] = (stats[stat] ?? 0) + delta
      }

      // Learn new ability at this level if the table lists one.
      const learned = this.params.learn_at_level?.[new_level]
      if (learned) {
        const book = (props.Spellbook ?? (props.Spellbook = { spells: [] })) as
          { spells: string[] }
        if (!book.spells.includes(learned)) {
          book.spells.push(learned)
        }
      }

      break
    }

    // Publish a world-flag condition for DialogTree / cutscene systems.
    try {
      writeWorldFlag(this.game, `${target}.leveled_up`, true)
      writeWorldFlag(this.game, `${target}.level`, new_level)
    } catch { /* world_flags may not be in scope for all scene shapes */ }
  }
}

mechanicRegistry.register('LevelUpProgression', (instance, game) => {
  const rt = new LevelUpProgressionRuntime(instance)
  rt.init(game)
  return rt
})
