// ChipMusic — Phase 5 audio-extension mechanic (v1.1).
//
// Instantiates a ChipSynth driven by the engine's AudioEngine. Handles
// base_track playback, N parallel-indexed overlay_tracks (each gated on
// an overlay_conditions[i] key), autoplay_on/stop_on flow hooks, and
// bpm/mixer MechanicRef live-deref at scheduler-tick granularity.
//
// Exposed fields (for HUD + sibling mechanics):
//   is_playing       — boolean, any base/overlay handle alive
//   current_beat     — number, beats elapsed on base track
//   active_layer     — index of last overlay added (0 = base only)
//   on_beat          — boolean, true in a ±beat_tolerance_ms window
//   off_beat         — inverse of on_beat
//   channel_gain.X   — 0..1, last mixer value for X ∈ pulse1/2/triangle/
//                      noise/wave
//
// Cross-mechanic refs (bpm, mixer) resolve by:
//   1) game.getMechanicField(id, field) if the host exposes that;
//   2) world_flags[`${id}.${field}`] as a fallback;
//   3) default (bpm=120, mixer=1) when neither is available.

import type { Game } from '../../game/game'
import type {
  ChipMusicParams,
  ChipMusicTrack,
  MechanicInstance,
  MechanicRef,
  MixerValue,
} from '../schema'
import { AudioEngine } from '../../audio/engine'
import { ChipSynth, type ChipHandle } from '../../audio/chipsynth'
import { flagTruthy } from './world_flags'
import { mechanicRegistry, type MechanicRuntime } from './index'

const DEFAULT_BEAT_TOLERANCE_MS = 100
const DEFAULT_CROSSFADE_MS = 500

class ChipMusicRuntime implements MechanicRuntime {
  private params: ChipMusicParams
  private game!: Game
  private engine: AudioEngine | null = null
  private synth: ChipSynth | null = null
  private baseHandle: ChipHandle | null = null
  private overlayHandles: Array<ChipHandle | null> = []
  private startedAtMs: number | null = null
  private autoplayArmed: boolean
  private stopped = false
  private lastMixer: Record<string, number> = {}

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as ChipMusicParams
    this.autoplayArmed = this.params.autoplay_on !== undefined
  }

  init(game: Game): void {
    this.game = game
    try {
      this.engine = this.resolveEngine(game)
      this.engine.init()
      this.synth = new ChipSynth(this.engine)
    } catch {
      // Headless test runners (no AudioContext) — keep the runtime
      // alive but silent. expose() still publishes is_playing=false.
      this.engine = null
      this.synth = null
    }
    if (!this.autoplayArmed) this.startBase()
  }

  update(_dt: number): void {
    if (this.stopped) return
    if (this.autoplayArmed && this.checkCondition(this.params.autoplay_on)) {
      this.autoplayArmed = false
      this.startBase()
    }
    if (this.params.stop_on && this.checkCondition(this.params.stop_on)) {
      this.stopAll()
      return
    }
    this.updateOverlays()
  }

  dispose(): void {
    this.stopAll()
  }

  expose(): Record<string, unknown> {
    const beat = this.currentBeat()
    const tolBeats = this.beatToleranceBeats()
    const fractional = beat - Math.floor(beat)
    const nearBeat = fractional <= tolBeats || fractional >= 1 - tolBeats
    const activeLayer = this.overlayHandles.reduce(
      (acc, h, i) => (h ? i + 1 : acc), 0,
    )
    const out: Record<string, unknown> = {
      is_playing: this.synth?.playing ?? false,
      current_beat: beat,
      active_layer: activeLayer,
      on_beat: this.synth?.playing ? nearBeat : false,
      off_beat: this.synth?.playing ? !nearBeat : false,
    }
    for (const [ch, v] of Object.entries(this.lastMixer)) {
      out[`channel_gain.${ch}`] = v
    }
    return out
  }

  // ───────── internals ─────────

  private resolveEngine(game: Game): AudioEngine {
    const existing = (game as unknown as { audio?: unknown }).audio
    if (existing instanceof AudioEngine) return existing
    return new AudioEngine()
  }

  private startBase(): void {
    if (!this.synth || this.baseHandle) return
    this.baseHandle = this.synth.play(this.params.base_track,
      { loop: this.params.base_track.loop })
    this.startedAtMs = performance.now()
    this.noteMixerValues(this.params.base_track)
  }

  private updateOverlays(): void {
    const tracks = this.params.overlay_tracks ?? []
    const conds = this.params.overlay_conditions ?? []
    // Parallel-indexed with overlay_tracks. Validator enforces
    // equal length, so mismatched arrays shouldn't hit the runtime.
    const n = Math.min(tracks.length, conds.length)
    if (this.overlayHandles.length !== n) {
      this.overlayHandles.length = n
      this.overlayHandles.fill(null, 0, n)
    }
    for (let i = 0; i < n; i++) {
      const active = this.checkCondition(conds[i])
      const current = this.overlayHandles[i]
      if (active && !current && this.synth && this.baseHandle) {
        this.overlayHandles[i] = this.synth.play(tracks[i],
          { loop: tracks[i].loop })
        this.noteMixerValues(tracks[i])
      } else if (!active && current) {
        this.synth?.stop(current, /* releaseTail */ true)
        this.overlayHandles[i] = null
      }
    }
  }

  private stopAll(): void {
    this.stopped = true
    for (const h of this.overlayHandles) {
      if (h) this.synth?.stop(h, /* releaseTail */ true)
    }
    this.overlayHandles.length = 0
    if (this.baseHandle) {
      this.synth?.stop(this.baseHandle, /* releaseTail */ true)
      this.baseHandle = null
    }
  }

  private checkCondition(key: string | undefined): boolean {
    if (!key) return false
    if (flagTruthy(this.game, key)) return true
    // Also read via game-level condition source if the host exposes
    // one — keeps the mechanic functional outside the world_flags
    // pipeline (used by some engines' condition emitters).
    const host = this.game as unknown as {
      conditionTruthy?: (k: string) => boolean
    }
    return host.conditionTruthy?.(key) === true
  }

  private resolveRef(
    value: number | MixerValue | MechanicRef | undefined,
    fallback: number,
  ): number {
    if (value === undefined) return fallback
    if (typeof value === 'number') return Number.isFinite(value) ? value : fallback
    const ref = value as MechanicRef
    const id = ref.mechanic_ref
    const field = ref.field
    if (!id || !field) return fallback

    const host = this.game as unknown as {
      getMechanicField?: (id: string, field: string) => unknown
    }
    const v = host.getMechanicField?.(id, field)
    if (typeof v === 'number' && Number.isFinite(v)) return v

    const scene = this.game.sceneManager?.activeScene?.() as
      { properties?: Record<string, unknown> } | undefined
    const flags = scene?.properties?.world_flags as
      Record<string, unknown> | undefined
    const flagValue = flags?.[`${id}.${field}`]
    if (typeof flagValue === 'number' && Number.isFinite(flagValue)) {
      return flagValue
    }
    return fallback
  }

  private noteMixerValues(track: ChipMusicTrack): void {
    for (const [ch, mv] of Object.entries(track.mixer ?? {})) {
      this.lastMixer[ch] = this.resolveRef(mv as MixerValue, 1)
    }
  }

  private currentBeat(): number {
    if (!this.baseHandle || this.startedAtMs === null) return 0
    const bpm = this.resolveRef(this.params.base_track.bpm, 120)
    const elapsedSec = (performance.now() - this.startedAtMs) / 1000
    return elapsedSec * (bpm / 60)
  }

  private beatToleranceBeats(): number {
    const ms = this.params.beat_tolerance_ms ?? DEFAULT_BEAT_TOLERANCE_MS
    const bpm = this.resolveRef(this.params.base_track.bpm, 120)
    const beatSec = 60 / Math.max(1, bpm)
    return (ms / 1000) / beatSec
  }
}

// Silence unused-import for DEFAULT_CROSSFADE_MS — kept as spec
// anchor for the planned per-overlay crossfade implementation in
// v1.1.2 (ChipSynth currently does release-tail on stop).
void DEFAULT_CROSSFADE_MS

mechanicRegistry.register('ChipMusic', (instance, game) => {
  const rt = new ChipMusicRuntime(instance)
  rt.init(game)
  return rt
})
