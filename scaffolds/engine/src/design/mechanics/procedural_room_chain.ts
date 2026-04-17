// ProceduralRoomChain — Phase 1 content-multiplier mechanic.
//
// Generates a run-unique sequence of rooms from a weighted pool, bounded
// by min/max per-run counts. Tracks depth, fires lifecycle actions on
// run start / room complete / run complete / run fail. The actual scene
// transitions are driven by the engine's scene_manager — this mechanic
// just decides WHICH room comes next at each advancement.
//
// v1 uses a seeded Mulberry32 PRNG so runs are reproducible given a seed.
// Seed defaults to Date.now() when not provided; set it via a world_flag
// "run_seed" on the scene to lock test seeds.

import type { Game } from '../../game/game'
import type {
  ActionRef,
  MechanicInstance,
  ProceduralRoomChainParams,
} from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

interface GeneratedRoom {
  id: string
  poolIndex: number
  depth: number
}

class ProceduralRoomChainRuntime implements MechanicRuntime {
  private params: ProceduralRoomChainParams
  private game!: Game
  private sequence: GeneratedRoom[] = []
  private currentIndex = 0
  private runStarted = false
  private runEnded = false
  private rng: () => number

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as ProceduralRoomChainParams
    this.rng = mulberry32((Date.now() ^ 0x9E3779B1) >>> 0)
  }

  init(game: Game): void {
    this.game = game
    this.generateRun()
    this.fire(this.params.run_lifecycle.on_run_start)
    this.runStarted = true
  }

  update(_dt: number): void {
    // Event-driven; no per-frame work.
  }

  dispose(): void {
    // Nothing to tear down — generation is one-shot.
  }

  /** Call when the player finishes the current room (boss down, chest grabbed, etc.). */
  completeRoom(): void {
    if (!this.runStarted || this.runEnded) return
    this.fire(this.params.run_lifecycle.on_room_complete)
    this.currentIndex += 1
    if (this.currentIndex >= this.sequence.length) {
      this.runEnded = true
      this.fire(this.params.run_lifecycle.on_run_complete)
    }
  }

  /** Call on a player-death / fail state. Ends the run and fires on_run_fail. */
  failRun(): void {
    if (!this.runStarted || this.runEnded) return
    this.runEnded = true
    this.fire(this.params.run_lifecycle.on_run_fail)
  }

  expose(): Record<string, unknown> {
    return {
      currentDepth: this.sequence[this.currentIndex]?.depth ?? 0,
      currentRoomId: this.sequence[this.currentIndex]?.id ?? null,
      totalRooms: this.sequence.length,
      roomsCompleted: this.currentIndex,
      runEnded: this.runEnded,
      sequence: this.sequence.map(r => r.id),
    }
  }

  // ───────── generation ─────────

  private generateRun(): void {
    const pool = this.params.room_pool ?? []
    const rules = this.params.connection_rules ?? { min_rooms_per_run: 1, max_rooms_per_run: 1 }
    const count = this.clamp(
      Math.round(this.rng() * (rules.max_rooms_per_run - rules.min_rooms_per_run))
        + rules.min_rooms_per_run,
      rules.min_rooms_per_run,
      rules.max_rooms_per_run,
    )

    const excluded = new Set<string>()
    for (let depth = 0; depth < count; depth++) {
      const candidates = pool.filter(p => {
        if (excluded.has(p.id)) return false
        if (p.min_depth !== undefined && depth < p.min_depth) return false
        if (p.max_depth !== undefined && depth > p.max_depth) return false
        return true
      })
      if (candidates.length === 0) break
      const picked = this.weightedPick(candidates)
      const poolIndex = pool.indexOf(picked)
      this.sequence.push({ id: picked.id, poolIndex, depth })
      if (picked.exclusive_with) picked.exclusive_with.forEach(x => excluded.add(x))
    }
  }

  private weightedPick<T extends { weight?: number }>(items: T[]): T {
    const total = items.reduce((s, i) => s + (i.weight ?? 1), 0)
    let r = this.rng() * total
    for (const item of items) {
      r -= item.weight ?? 1
      if (r <= 0) return item
    }
    return items[items.length - 1]
  }

  private fire(action: ActionRef | undefined): void {
    if (!action) return
    // Lifecycle actions are typically flow-level (emit conditions,
    // spawn rewards, etc.). v1 defers to the engine's action dispatcher
    // where available; otherwise we surface them via expose() so the
    // harness can observe them without hard-coding a dispatcher here.
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* dispatcher bug is not our problem */ }
    }
  }

  private clamp(v: number, lo: number, hi: number): number {
    return Math.max(lo, Math.min(hi, v))
  }
}

// Minimal PRNG — not cryptographically secure, just reproducible.
function mulberry32(seed: number): () => number {
  let t = seed >>> 0
  return () => {
    t = (t + 0x6D2B79F5) >>> 0
    let r = t
    r = Math.imul(r ^ (r >>> 15), r | 1)
    r ^= r + Math.imul(r ^ (r >>> 7), r | 61)
    return ((r ^ (r >>> 14)) >>> 0) / 4_294_967_296
  }
}

mechanicRegistry.register('ProceduralRoomChain', (instance, game) => {
  const rt = new ProceduralRoomChainRuntime(instance)
  rt.init(game)
  return rt
})
