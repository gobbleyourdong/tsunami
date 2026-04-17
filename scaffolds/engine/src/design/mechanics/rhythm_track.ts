// RhythmTrack — Phase 1 content-multiplier mechanic.
//
// Spawns `beat_spawn_archetype` entities on a bpm-driven metronome, tracks
// hit/miss windows for player input, publishes score + combo fields for
// HUD/ScoreCombos consumers.
//
// v1 scope: audio playback is wired via Game's audio system when
// audio_ref resolves to a loaded asset; missing audio degrades to a
// silent metronome that still drives spawn cadence (useful for tests).

import type { Game } from '../../game/game'
import type {
  MechanicInstance,
  RhythmTrackParams,
} from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class RhythmTrackRuntime implements MechanicRuntime {
  private game!: Game
  private params: RhythmTrackParams
  private beatIntervalMs: number
  private sinceLastBeatMs = 0
  private beatsSpawned = 0
  private hits = 0
  private misses = 0
  private combo = 0
  private maxCombo = 0
  // Timestamps of beats that have spawned but haven't been hit or missed.
  private pendingBeats: Array<{ spawnedAtMs: number }> = []
  private disposed = false

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as RhythmTrackParams
    // Minute / beats-per-minute → ms per beat. Denominator safety below.
    const bpm = this.params.bpm && this.params.bpm > 0 ? this.params.bpm : 120
    this.beatIntervalMs = 60_000 / bpm
  }

  init(game: Game): void {
    this.game = game
    // Audio hookup is opt-in — skip silently if the asset isn't loaded.
    // Engine's audio system exposes `play(name, opts)` when an asset of
    // that name has been registered by the project's assets pipeline.
    const audio = (game as unknown as Record<string, unknown>).audio as
      Record<string, (name: string, opts?: Record<string, unknown>) => void> | undefined
    if (audio?.play && this.params.audio_ref) {
      try { audio.play(this.params.audio_ref, { loop: false }) }
      catch { /* silent — degrade to metronome-only */ }
    }
  }

  update(dt: number): void {
    if (this.disposed) return
    const dtMs = dt * 1000
    this.sinceLastBeatMs += dtMs

    while (this.sinceLastBeatMs >= this.beatIntervalMs) {
      this.sinceLastBeatMs -= this.beatIntervalMs
      this.spawnBeat()
    }

    // Age out missed beats (beyond the hit window).
    const now = performance.now()
    while (this.pendingBeats.length > 0
           && now - this.pendingBeats[0].spawnedAtMs > this.params.hit_window_ms) {
      this.pendingBeats.shift()
      this.misses += 1
      this.combo = 0
    }
  }

  /** Called by input wiring when the player attempts a beat hit. Returns true on hit. */
  attemptHit(timestampMs: number = performance.now()): boolean {
    // Find the closest pending beat whose spawn timestamp is within the
    // hit window. If found, consume it (hit). Otherwise, no pending beat
    // → miss the input.
    for (let i = 0; i < this.pendingBeats.length; i++) {
      const delta = Math.abs(timestampMs - this.pendingBeats[i].spawnedAtMs)
      if (delta <= this.params.hit_window_ms) {
        this.pendingBeats.splice(i, 1)
        this.hits += 1
        this.combo += 1
        if (this.combo > this.maxCombo) this.maxCombo = this.combo
        return true
      }
    }
    this.combo = 0
    return false
  }

  dispose(): void {
    this.disposed = true
    this.pendingBeats.length = 0
  }

  expose(): Record<string, unknown> {
    return {
      hits: this.hits,
      misses: this.misses,
      combo: this.combo,
      maxCombo: this.maxCombo,
      beatsSpawned: this.beatsSpawned,
      // Handy for debugging the mechanic externally.
      bpm: this.params.bpm,
    }
  }

  private spawnBeat(): void {
    this.beatsSpawned += 1
    this.pendingBeats.push({ spawnedAtMs: performance.now() })
    // Optional visible spawn — in scope for the v1 runtime, actual mesh
    // spawn goes through SceneManager's active scene. Guard in case the
    // scene hasn't been populated yet (first-frame race on scene_goto).
    try {
      const active = this.game.sceneManager?.activeScene?.()
      if (active && typeof (active as Record<string, unknown>).spawn === 'function') {
        (active as Record<string, (type: string, opts?: Record<string, unknown>) => void>)
          .spawn(this.params.beat_spawn_archetype as unknown as string, {
            position: [0, 0, 0],
            properties: { spawnedByMechanic: this.instance.id },
          })
      }
    } catch { /* scene not ready; drop this beat's visual */ }
  }
}

// Side-effect register at module load — matches the pattern described in
// mechanics/index.ts. Importing any Phase 1 mechanic file pulls in its
// runtime automatically.
mechanicRegistry.register('RhythmTrack', (instance, game) => {
  const rt = new RhythmTrackRuntime(instance)
  rt.init(game)
  return rt
})
