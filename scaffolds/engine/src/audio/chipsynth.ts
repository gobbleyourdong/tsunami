// chipsynth.ts — 4+1 channel chiptune synthesizer (Phase 3 of audio v1.1).
//
// Five channels, no external deps, pure Web Audio:
//
//   pulse1, pulse2 — square wave via createPeriodicWave with 4 duty
//                    cycles (0.125, 0.25, 0.5, 0.75). Four PeriodicWaves
//                    pre-computed at init; note switches wave node.
//   triangle       — built-in OscillatorNode type='triangle'.
//   noise          — AudioBufferSource of white noise, drum-preset
//                    envelope (DRUM_PRESETS table).
//   wave (opt)     — custom PeriodicWave from 32-sample ChipMusicTrack
//                    .wave_table (4-bit, 0..15). Only active when the
//                    track provides a wave_table.
//
// ADSR via GainNode.gain automation per note.
// Scheduler: setInterval(25 ms) lookahead that schedules the next
// 100 ms of note events into AudioContext.currentTime. Routes through
// engine.channelGain('music') (or 'ambient' when ChipMusicParams.channel
// says so). Clean stopAll() / per-handle stop() so flow transitions
// don't leave oscillators alive.
//
// BPM / mixer can be numbers OR {mechanic_ref, field}. The scheduler
// resolves refs at each tick, so a Difficulty.level change ramps the
// tempo/mixer at tick granularity (25 ms).

import type { AudioEngine } from './engine'

// ─────────────────────────────────────────────────────────────
//   Types — subset duplicated from schema.ts so sfxr/chipsynth can
//   land before Phase 4 reshapes schema.ts. Phase 4 re-exports from
//   schema.ts; engine modules keep their own source of truth.
// ─────────────────────────────────────────────────────────────

export type ChipChannel = 'pulse1' | 'pulse2' | 'triangle' | 'noise' | 'wave'

export interface EnvelopeADSR {
  attack: number   // sec
  decay: number    // sec
  sustain: number  // 0..1
  release: number  // sec
}

export interface NoteEvent {
  time: number        // beats
  note: string        // 'C4' | 'D#5' | 'R' (rest) | drum name for noise
  duration: number    // beats
  velocity?: number
  envelope?: EnvelopeADSR
  dutyCycle?: 0.125 | 0.25 | 0.5 | 0.75
  vibrato?: { rate: number; depth: number }
}

export interface MechanicRef {
  mechanic_ref: string   // MechanicId
  field: string
}

export type MixerValue = number | (MechanicRef & { ramp_ms?: number })

export interface ChipMusicTrack {
  bpm: number | MechanicRef
  bars?: number
  loop: boolean
  loopStart?: number
  channels: Partial<Record<ChipChannel, NoteEvent[]>>
  mixer?: Partial<Record<ChipChannel, MixerValue>>
  wave_table?: number[]
}

// ─────────────────────────────────────────────────────────────
//   Drum presets — noise-channel named drums
// ─────────────────────────────────────────────────────────────

interface DrumPreset {
  freq: number         // resonance freq (Hz) of LPF
  durationMs: number   // envelope length
  startGain: number    // initial amp (noise only)
  lpCutoff?: number    // lowpass cutoff Hz (undefined = pass-thru)
  lpSweep?: boolean    // if true, cutoff sweeps down over envelope
}

const DRUM_PRESETS: Record<string, DrumPreset> = {
  kick:       { freq: 80,  durationMs: 140, startGain: 1.0, lpCutoff:   200 },
  snare:      { freq: 300, durationMs: 200, startGain: 0.8, lpCutoff:  3500 },
  hat:        { freq: 8000, durationMs: 40, startGain: 0.4, lpCutoff: 10000 },
  hat_closed: { freq: 8000, durationMs: 40, startGain: 0.4, lpCutoff: 10000 },
  hat_open:   { freq: 6000, durationMs: 220, startGain: 0.4, lpCutoff: 10000, lpSweep: true },
  crash:      { freq: 4000, durationMs: 600, startGain: 0.5, lpCutoff: 10000, lpSweep: true },
  tom_hi:     { freq: 200, durationMs: 220, startGain: 0.8, lpCutoff:  1200 },
  tom_lo:     { freq: 120, durationMs: 260, startGain: 0.9, lpCutoff:   800 },
}

// ─────────────────────────────────────────────────────────────
//   Scientific pitch notation → Hz
// ─────────────────────────────────────────────────────────────

const NOTE_OFFSET: Record<string, number> = {
  C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4,
  F: 5, 'F#': 6, Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9, 'A#': 10, Bb: 10, B: 11,
}

function noteToHz(note: string): number | null {
  if (note === 'R' || note === 'r' || note === '') return null
  const m = note.match(/^([A-Ga-g][#b]?)(-?\d+)$/)
  if (!m) return null
  const letter = m[1][0].toUpperCase() + (m[1].slice(1) ?? '')
  const octave = parseInt(m[2], 10)
  const semitone = NOTE_OFFSET[letter]
  if (semitone === undefined) return null
  // Midi # 69 = A4 = 440 Hz.
  const midi = (octave + 1) * 12 + semitone
  return 440 * Math.pow(2, (midi - 69) / 12)
}


// ─────────────────────────────────────────────────────────────
//   ChipSynth — main class
// ─────────────────────────────────────────────────────────────

export interface ChipHandle {
  id: number
  track: ChipMusicTrack
  /** Cancel the scheduler + stop any playing note nodes. */
  stop(releaseTail?: boolean): void
}

interface ActiveHandle extends ChipHandle {
  schedulerId: ReturnType<typeof setInterval> | null
  nextNoteBeat: number
  startTime: number            // ctx.currentTime at start
  beatsScheduled: number
  activeNodes: Array<{ osc?: OscillatorNode; src?: AudioBufferSourceNode; gain: GainNode }>
  bpmRefResolver: () => number
  mixerRefResolvers: Record<string, () => number>
  channelOutputGain: GainNode
}

const LOOKAHEAD_MS = 25      // scheduler interval
const SCHEDULE_AHEAD_SEC = 0.1  // schedule events this far into the future

export class ChipSynth {
  private engine: AudioEngine
  private handles = new Map<number, ActiveHandle>()
  private nextId = 1
  private noisBuffer: AudioBuffer | null = null
  // Keyed by either a numeric duty cycle (e.g. 125 for 12.5 %) or the
  // literal 'wave' for the track's custom wave-table PeriodicWave.
  private periodicWaves: Record<string, PeriodicWave> = {}

  constructor(engine: AudioEngine) {
    this.engine = engine
  }

  get playing(): boolean { return this.handles.size > 0 }

  play(track: ChipMusicTrack, options?: { loop?: boolean; startTime?: number }): ChipHandle {
    const ctx = this.engine.context
    if (!ctx) throw new Error('ChipSynth.play: engine not initialised')
    this.ensurePrecomputed(ctx, track)

    const output = this.engine.channelGain('music') ?? ctx.destination as unknown as GainNode

    const id = this.nextId++
    const bpmResolver = this.makeRefResolver(track.bpm, 120)
    const mixerResolvers: Record<string, () => number> = {}
    for (const [ch, mv] of Object.entries(track.mixer ?? {})) {
      mixerResolvers[ch] = this.makeRefResolver(mv as MixerValue, 1)
    }

    const channelGain = ctx.createGain()
    channelGain.gain.value = 1
    channelGain.connect(output)

    const handle: ActiveHandle = {
      id, track,
      schedulerId: null,
      nextNoteBeat: 0,
      startTime: options?.startTime ?? ctx.currentTime,
      beatsScheduled: 0,
      activeNodes: [],
      bpmRefResolver: bpmResolver,
      mixerRefResolvers: mixerResolvers,
      channelOutputGain: channelGain,
      stop: (releaseTail?: boolean) => this.stopHandle(handle, releaseTail ?? false),
    }

    handle.schedulerId = setInterval(() => this.tick(handle),
      LOOKAHEAD_MS) as unknown as ReturnType<typeof setInterval>
    this.handles.set(id, handle)
    // Fire one tick immediately so we don't wait 25 ms for first note.
    this.tick(handle)
    return handle
  }

  stop(handle: ChipHandle, releaseTail = false): void {
    const active = this.handles.get(handle.id)
    if (!active) return
    this.stopHandle(active, releaseTail)
  }

  stopAll(): void {
    for (const h of [...this.handles.values()]) this.stopHandle(h, false)
  }

  // ───────── internals ─────────

  private stopHandle(handle: ActiveHandle, releaseTail: boolean): void {
    if (handle.schedulerId !== null) {
      clearInterval(handle.schedulerId as unknown as number)
      handle.schedulerId = null
    }
    const ctx = this.engine.context
    const now = ctx?.currentTime ?? 0
    for (const n of handle.activeNodes) {
      try {
        if (releaseTail) {
          n.gain.gain.setTargetAtTime(0, now, 0.05)
          n.osc?.stop(now + 0.2)
          n.src?.stop(now + 0.2)
        } else {
          n.gain.gain.cancelScheduledValues(now)
          n.gain.gain.setValueAtTime(0, now)
          n.osc?.stop(now)
          n.src?.stop(now)
        }
      } catch { /* node already stopped */ }
    }
    handle.activeNodes.length = 0
    this.handles.delete(handle.id)
  }

  private tick(handle: ActiveHandle): void {
    const ctx = this.engine.context
    if (!ctx) return
    const now = ctx.currentTime
    const bpm = handle.bpmRefResolver()
    const secPerBeat = 60 / Math.max(1, bpm)
    // Live-update mixer gains.
    for (const [ch, resolver] of Object.entries(handle.mixerRefResolvers)) {
      // v1: apply to the channel's scheduled notes retroactively via
      // the channelOutputGain (acts as a master trim). Per-channel
      // mixer nodes would require maintaining 5 gain nodes per handle
      // — deferred to v1.1.2 (spec note in schema.ts).
      void ch  // silence unused — kept for future per-channel routing
      handle.channelOutputGain.gain.setTargetAtTime(
        resolver(), now, 0.02,
      )
    }

    const scheduleUntilBeat = handle.beatsScheduled
      + SCHEDULE_AHEAD_SEC / secPerBeat

    for (const [chName, notes] of Object.entries(handle.track.channels ?? {})) {
      for (const note of notes ?? []) {
        if (note.time < handle.beatsScheduled) continue
        if (note.time >= scheduleUntilBeat) continue
        const when = handle.startTime + note.time * secPerBeat
        const durSec = note.duration * secPerBeat
        this.scheduleNote(handle, chName as ChipChannel, note, when, durSec)
      }
    }

    // Loop handling — when we cross the end, rewind to loopStart.
    const endBeat = handle.track.bars
      ? handle.track.bars * 4
      : this.computeTrackLength(handle.track)
    handle.beatsScheduled = scheduleUntilBeat
    if (handle.track.loop && scheduleUntilBeat >= endBeat) {
      const loopStart = handle.track.loopStart ?? 0
      handle.beatsScheduled = loopStart
      handle.startTime += (endBeat - loopStart) * secPerBeat
    }
  }

  private scheduleNote(
    handle: ActiveHandle,
    channel: ChipChannel,
    note: NoteEvent,
    when: number,
    durSec: number,
  ): void {
    const ctx = this.engine.context
    if (!ctx) return

    if (channel === 'noise') {
      this.scheduleDrumNote(handle, note, when)
      return
    }
    const hz = noteToHz(note.note)
    if (hz === null) return  // rest

    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    gain.gain.value = 0
    osc.connect(gain)
    gain.connect(handle.channelOutputGain)

    if (channel === 'pulse1' || channel === 'pulse2') {
      const duty = note.dutyCycle ?? 0.5
      const wave = this.periodicWaves[duty * 1000]
      if (wave) osc.setPeriodicWave(wave)
      else osc.type = 'square'
    } else if (channel === 'triangle') {
      osc.type = 'triangle'
    } else if (channel === 'wave') {
      const wave = this.periodicWaves.wave
      if (wave) osc.setPeriodicWave(wave)
      else osc.type = 'sine'
    }

    osc.frequency.setValueAtTime(hz, when)

    // Vibrato — LFO on frequency.
    if (note.vibrato) {
      const lfo = ctx.createOscillator()
      lfo.frequency.value = note.vibrato.rate
      const lfoGain = ctx.createGain()
      lfoGain.gain.value = hz * (Math.pow(2, note.vibrato.depth / 12) - 1)
      lfo.connect(lfoGain); lfoGain.connect(osc.frequency)
      lfo.start(when); lfo.stop(when + durSec + 0.1)
    }

    const env = note.envelope ?? { attack: 0.005, decay: 0.05,
                                    sustain: (note.velocity ?? 1) * 0.7, release: 0.05 }
    gain.gain.setValueAtTime(0, when)
    gain.gain.linearRampToValueAtTime(note.velocity ?? 1, when + env.attack)
    gain.gain.linearRampToValueAtTime(env.sustain, when + env.attack + env.decay)
    gain.gain.setValueAtTime(env.sustain, when + durSec)
    gain.gain.linearRampToValueAtTime(0, when + durSec + env.release)

    osc.start(when)
    osc.stop(when + durSec + env.release + 0.02)
    handle.activeNodes.push({ osc, gain })
  }

  private scheduleDrumNote(handle: ActiveHandle, note: NoteEvent, when: number): void {
    const ctx = this.engine.context
    if (!ctx || !this.noisBuffer) return
    const preset = DRUM_PRESETS[note.note]
    if (!preset) return  // unknown drum = drop

    const src = ctx.createBufferSource()
    src.buffer = this.noisBuffer
    src.loop = true
    const gain = ctx.createGain()
    const lp = ctx.createBiquadFilter()
    lp.type = 'lowpass'
    lp.Q.value = 1
    lp.frequency.setValueAtTime(preset.lpCutoff ?? 20000, when)
    if (preset.lpSweep) {
      lp.frequency.linearRampToValueAtTime(200, when + preset.durationMs / 1000)
    }

    src.connect(lp); lp.connect(gain); gain.connect(handle.channelOutputGain)

    const dur = preset.durationMs / 1000
    gain.gain.setValueAtTime(preset.startGain * (note.velocity ?? 1), when)
    gain.gain.exponentialRampToValueAtTime(0.001, when + dur)

    src.start(when)
    src.stop(when + dur + 0.02)
    handle.activeNodes.push({ src, gain })
  }

  private ensurePrecomputed(ctx: AudioContext, track: ChipMusicTrack): void {
    // Pulse-wave PeriodicWaves for each canonical duty cycle.
    for (const duty of [0.125, 0.25, 0.5, 0.75]) {
      const key = duty * 1000
      if (this.periodicWaves[key]) continue
      this.periodicWaves[key] = this.makePulseWave(ctx, duty)
    }
    // Wave-channel custom PeriodicWave from track.wave_table.
    if (track.wave_table && track.wave_table.length > 0) {
      this.periodicWaves.wave = this.makeCustomWave(ctx, track.wave_table)
    }
    // Shared noise buffer.
    if (!this.noisBuffer) {
      const buf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate)
      const data = buf.getChannelData(0)
      for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
      this.noisBuffer = buf
    }
  }

  private makePulseWave(ctx: AudioContext, duty: number): PeriodicWave {
    // Fourier series of a pulse with given duty cycle, harmonics up to n=32.
    const n = 32
    const real = new Float32Array(n + 1)
    const imag = new Float32Array(n + 1)
    for (let k = 1; k <= n; k++) {
      imag[k] = (2 / (k * Math.PI)) * Math.sin(Math.PI * k * duty)
    }
    return ctx.createPeriodicWave(real, imag, { disableNormalization: false })
  }

  private makeCustomWave(ctx: AudioContext, table: number[]): PeriodicWave {
    // DFT of the 32-sample 4-bit wave table → real/imag harmonics.
    const n = Math.min(32, table.length)
    const normalized = table.slice(0, n).map(v => (v / 15) * 2 - 1)  // 0..15 → -1..1
    const real = new Float32Array(n / 2 + 1)
    const imag = new Float32Array(n / 2 + 1)
    for (let k = 0; k <= n / 2; k++) {
      let r = 0, im = 0
      for (let t = 0; t < n; t++) {
        const theta = (2 * Math.PI * k * t) / n
        r += normalized[t] * Math.cos(theta)
        im -= normalized[t] * Math.sin(theta)
      }
      real[k] = r / n
      imag[k] = im / n
    }
    return ctx.createPeriodicWave(real, imag, { disableNormalization: false })
  }

  private makeRefResolver(value: number | MechanicRef | MixerValue, fallback: number): () => number {
    if (typeof value === 'number') return () => value
    if (value && typeof value === 'object' && 'mechanic_ref' in value) {
      const ref = value as MechanicRef
      return () => {
        const active = this.engine.context
        if (!active) return fallback
        // v1 hook: read from scene.properties.mechanic_runtimes[ref.mechanic_ref].expose()[ref.field]
        const sceneMgrShape = (this.engine as unknown as Record<string, unknown>).sceneManager as
          Record<string, unknown> | undefined
        const activeScene = sceneMgrShape?.activeScene as (() => Record<string, unknown>) | undefined
        if (typeof activeScene !== 'function') return fallback
        const scene = activeScene()
        const runtimes = ((scene.properties ?? {}) as Record<string, unknown>).mechanic_runtimes as
          Record<string, { expose?(): Record<string, unknown> }> | undefined
        const r = runtimes?.[ref.mechanic_ref]?.expose?.()
        const v = r?.[ref.field]
        return typeof v === 'number' ? v : fallback
      }
    }
    return () => fallback
  }

  private computeTrackLength(track: ChipMusicTrack): number {
    let max = 0
    for (const notes of Object.values(track.channels ?? {})) {
      for (const n of notes ?? []) {
        const end = n.time + n.duration
        if (end > max) max = end
      }
    }
    return max || 4
  }
}
