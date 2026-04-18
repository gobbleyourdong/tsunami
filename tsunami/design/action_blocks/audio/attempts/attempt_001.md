# Audio extension — attempt 001

> Synthesis thread, fire 1. Content thread is at fire 1 with 5 priors,
> 3 tracks, 5 SFX seeds using placeholder shapes. This attempt lands
> the concrete shapes so they can lock in.

## Scope

Procedural audio for the action-blocks scaffold: **chiptune** (4-channel
tracker-style music) + **sfxr** (procedural retro SFX). Zero-dep, pure
Web Audio API. Schema-authorable by LLM.

Reference: `BRIEF.md` for cold-start; `engine/src/audio/engine.ts` for
existing playback layer (read this session, not duplicating).

## 1. Engine integration points (3 small additions to AudioEngine)

Don't rewrite `audio/engine.ts`. Add 3 methods to let extensions hook
in without owning their own `AudioContext`:

```ts
// add to AudioEngine class in engine.ts
class AudioEngine {
  // ... existing ...

  /** Public accessor for extensions (ChipSynth, custom DSP). */
  get context(): AudioContext | null { return this.ctx }

  /** Skip decode when caller already has an AudioBuffer (e.g., Sfxr). */
  loadRawBuffer(id: string, buffer: AudioBuffer): void {
    if (!this.ctx) this.init()
    this.buffers.set(id, buffer)
  }

  /** Gain node for a channel; extensions connect oscillators here. */
  channelGain(channel: AudioChannel): GainNode | null {
    return this.channelGains.get(channel) ?? this.masterGain
  }
}
```

Cost: ~10 lines. Does not alter existing behavior. Tests: existing
`audio/engine.test.ts` (if it exists) still passes; add 3 tests for
the new getters.

## 2. ChipSynth — 4-channel tracker synth

### Param types (TS)

```ts
// engine/src/audio/chipsynth.ts (public types — imported by schema)

export type ChipChannel = 'pulse1' | 'pulse2' | 'triangle' | 'noise'

export interface NoteEvent {
  time: number       // beats from track start (float)
  note: string       // 'C4', 'D#5', 'A2' — or 'R' for rest
  duration: number   // beats
  velocity?: number  // 0..1, default 1
  envelope?: {       // ADSR override for this note (default = channel default)
    attack?: number   // sec
    decay?: number
    sustain?: number  // 0..1 amplitude
    release?: number  // sec
  }
  // pulse-only
  dutyCycle?: number // 0.125 | 0.25 | 0.5 | 0.75 (NES-authentic set)
  // pulse/triangle
  vibrato?: { rate: number; depth: number } // Hz, semitones
}

export interface ChipChannelConfig {
  waveform: 'pulse' | 'triangle' | 'noise'
  defaultDuty?: number            // 0..1, pulse only
  defaultEnvelope?: EnvelopeADSR
  gain?: number                   // 0..1, per-channel volume
}

export interface EnvelopeADSR {
  attack: number
  decay: number
  sustain: number
  release: number
}

export interface ChipMusicTrack {
  bpm: number
  bars?: number                   // optional; inferred from max event time
  loop: boolean
  loopStart?: number              // beat to loop back to (default 0)
  channels: Partial<Record<ChipChannel, NoteEvent[]>>
  mixer?: Partial<Record<ChipChannel, number>>  // per-channel gain 0..1
}
```

### API

```ts
export class ChipSynth {
  constructor(audioEngine: AudioEngine)

  /** Compile a track, schedule against AudioContext clock, start. */
  play(track: ChipMusicTrack, options?: { loop?: boolean; startTime?: number }): ChipHandle

  /** Stop a playing track; optionally with release-tail. */
  stop(handle: ChipHandle, releaseTail?: boolean): void

  /** Stop all current tracks. */
  stopAll(): void

  /** Is anything playing. */
  get playing(): boolean
}

export interface ChipHandle { id: number; track: ChipMusicTrack }
```

### Implementation shape

- Scheduler pattern: `setInterval(25ms)` lookahead schedules next 100ms
  of note events via `osc.start(time)` / `gain.setValueAtTimeAtTime(...)`
  using `ctx.currentTime`. Avoid jitter.
- Per-note, construct OscillatorNode (pulse = square via custom
  PeriodicWave for N duty cycles; triangle = built-in; noise = AudioBufferSource
  of white noise loop).
- Envelope via GainNode: schedule attack ramp → decay ramp → sustain hold →
  release ramp on `noteOff(time)`.
- Route per-channel output → channel-level GainNode (for the `mixer`
  map) → `audioEngine.channelGain('music')`.
- Loop: at loop-start time minus 100ms, re-queue from `loopStart` beat.

**Cost estimate:** ~200 lines target. Scheduler + note compilation +
envelope routing + pulse/triangle/noise voice builders. One evening
for a programmer.

**Non-trivial bits:**
- Pulse wave with variable duty requires a `PeriodicWave` per duty
  cycle (pre-compute the 4 canonical NES duties at init).
- Noise channel: NES-authentic short/long LFSR is distinct from white
  noise. Start with white noise (simpler); LFSR variant later if
  wanted.
- Vibrato: LFO (low-freq OscillatorNode) routed to `frequency.value`
  via modulator gain.

## 3. Sfxr — procedural retro SFX

### Param type (TS)

27 params, following jsfxr canonical layout:

```ts
// engine/src/audio/sfxr.ts

export type SfxrWaveType = 'square' | 'sawtooth' | 'sine' | 'noise'

export interface SfxrParams {
  waveType: SfxrWaveType

  // Envelope
  envelopeAttack: number    // 0..1 (time, normalized)
  envelopeSustain: number   // 0..1 (time)
  envelopePunch: number     // 0..1 (sustain spike at start)
  envelopeDecay: number     // 0..1 (time)

  // Base frequency + slide
  baseFreq: number          // 0..1 (mapped to 30..8000 Hz)
  freqLimit: number         // 0..1 (lower bound, 0 = none)
  freqRamp: number          // -1..1 (slide over sustain)
  freqDeltaRamp: number     // -1..1 (slide of slide)

  // Vibrato
  vibratoStrength: number   // 0..1
  vibratoSpeed: number      // 0..1

  // Arpeggio (pitch jumps during sustain)
  arpMod: number            // -1..1 (pitch step)
  arpSpeed: number          // 0..1

  // Duty cycle (square only)
  duty: number              // 0..1
  dutyRamp: number          // -1..1

  // Retrigger
  repeatSpeed: number       // 0..1 (0 = no retrigger)

  // Flanger
  flangerOffset: number     // -1..1
  flangerRamp: number       // -1..1

  // Filters
  lpFilterCutoff: number    // 0..1
  lpFilterCutoffRamp: number
  lpFilterResonance: number
  hpFilterCutoff: number
  hpFilterCutoffRamp: number

  // Output
  masterVolume: number      // 0..1
  sampleRate: 44100 | 22050 | 11025
  sampleSize: 8 | 16
}
```

### API

```ts
export class Sfxr {
  constructor(audioEngine: AudioEngine)

  /** Render params to an AudioBuffer (mono). */
  generate(params: SfxrParams): AudioBuffer

  /** Convenience: generate + register with AudioEngine for play_sfx. */
  generateAndRegister(id: string, params: SfxrParams): void

  /** Randomized generator (seed-based, for serialization). */
  random(kind: 'pickup'|'laser'|'explosion'|'powerup'|'hit'|'jump'|'blip', seed?: number): SfxrParams
}
```

### Implementation shape

Port of jsfxr (DrPetter's original, MIT). Algorithm is a single
sample-loop — evaluate envelope, compute phase increment (with
slide/vibrato/arpeggio), sample waveform, apply LP/HP filter
(IIR biquad), apply flanger (delay line), write to buffer. ~300
lines target.

**Interop:** `generate(params)` returns AudioBuffer; caller passes to
`audioEngine.loadRawBuffer(id, buffer)`, then uses existing
`play(id, opts)`. Downstream Action `play_sfx` can inline the params
or reference a library.

**Cost estimate:** ~300 lines. Algorithmically straightforward port;
main work is the 27-param mapping and sample-rate resampling.

## 4. Schema deltas (to `reference/schema.ts`)

### ActionRef expansion

```ts
// add to the existing ActionRef union:
export type ActionRef =
  | ... existing 5 kinds ...
  | { kind: 'play_sfx';      params: SfxrParams }
  | { kind: 'play_sfx_ref';  library_ref: MechanicId; preset: string }
  | { kind: 'play_chiptune'; track_ref: MechanicId }
  | { kind: 'stop_chiptune'; track_ref: MechanicId; release_tail?: boolean }
```

**`play_sfx` vs `play_sfx_ref`:** inline params for one-offs; library
reference for repeated use (saves schema tokens). Validator checks
`library_ref` exists and `preset` is a known key in that library.

### New MechanicType values

```ts
export type MechanicType =
  | ... existing 15 ...
  | 'ChipMusic'
  | 'SfxLibrary'

export type MechanicParams =
  | ... existing ...
  | ChipMusicParams
  | SfxLibraryParams

export interface ChipMusicParams {
  track: ChipMusicTrack              // the ChipSynth input shape
  autoplay_on?: ConditionKey          // emit start on this condition
  stop_on?: ConditionKey              // emit stop on this condition
  channel: 'music' | 'ambient'        // routing hint
}

export interface SfxLibraryParams {
  sfx: Record<string, SfxrParams>     // named presets, referenced by ActionRef play_sfx_ref
}
```

### Validator additions (to `validate.ts`)

- `unknown_sfx_preset`: `play_sfx_ref.preset` is not a key in the
  referenced `SfxLibrary`.
- `invalid_chiptune_track`: track has a note with non-musical name or
  duration <= 0 or time < 0.
- `library_ref_not_sfx_library`: `play_sfx_ref.library_ref` points to a
  mechanic whose type is not `SfxLibrary`.

**Cost:** ~30 lines of validator logic + 3 new error cases.

## 5. Catalog entries (to `reference/catalog.ts`)

```ts
ChipMusic: {
  type: 'ChipMusic',
  description:
    '4-channel chiptune (2 pulse + triangle + noise) scheduled against ' +
    'game-time. Emits play/stop on named conditions.',
  example_params: {
    track: {
      bpm: 120, loop: true,
      channels: {
        pulse1: [{ time: 0, note: 'C5', duration: 0.5 }, /* ... */],
        triangle: [{ time: 0, note: 'C3', duration: 1.0 }, /* ... */],
      },
    },
    autoplay_on: 'scene_enter',
    stop_on: 'scene_exit',
    channel: 'music',
  },
  emits_fields: ['is_playing', 'current_beat'],
  common_patches: ['change BPM', 'swap track JSON', 'toggle loop'],
},

SfxLibrary: {
  type: 'SfxLibrary',
  description:
    'Named catalog of sfxr parameter sets. Referenced by ActionRef ' +
    "play_sfx_ref: { library_ref: 'sfxlib', preset: 'coin' }.",
  example_params: {
    sfx: {
      coin:        { waveType: 'square', envelopeAttack: 0.0, envelopeSustain: 0.05, /* ... */ },
      laser_small: { waveType: 'square', envelopeAttack: 0.0, envelopeSustain: 0.12, /* ... */ },
    },
  },
  common_patches: ['add preset', 'tune punch', 'shift base_freq'],
},
```

## 6. Three example ChipMusic tracks

Content thread (`audio/library/track_NNN.md`) is authoring the full
catalog. To unblock them, here's the **canonical JSON shape** they
should use — matches the `ChipMusicTrack` type above verbatim:

```json
{
  "bpm": 110,
  "loop": true,
  "channels": {
    "pulse1": [
      { "time": 0,    "note": "C5",  "duration": 0.5 },
      { "time": 0.5,  "note": "E5",  "duration": 0.5 },
      { "time": 1,    "note": "G5",  "duration": 0.5 },
      { "time": 1.5,  "note": "C6",  "duration": 0.5 }
    ],
    "pulse2": [
      { "time": 0,    "note": "E4",  "duration": 2,   "dutyCycle": 0.25 }
    ],
    "triangle": [
      { "time": 0,    "note": "C3",  "duration": 1 },
      { "time": 1,    "note": "G2",  "duration": 1 }
    ],
    "noise": [
      { "time": 0,    "note": "kick",  "duration": 0.25 },
      { "time": 0.5,  "note": "snare", "duration": 0.25 },
      { "time": 1,    "note": "kick",  "duration": 0.25 },
      { "time": 1.5,  "note": "snare", "duration": 0.25 }
    ]
  }
}
```

Noise channel uses named drum tokens (`kick`, `snare`, `hat_closed`,
`hat_open`, `crash`) mapped internally to LFSR seeds + envelopes —
content thread and I will converge on the exact mapping at attempt_002
if they want richer drums.

## 7. Prompt-scaffold integration (defer to content thread)

Content thread will add the "sound" subsection to
`tsunami/context/design_script.md`. My job on prompt-scaffold is just:
write the authoritative shape example for them to embed. Done above.

## 8. Ship criteria (v1.1 audio)

Green gates:

1. `chipsynth.ts` + `sfxr.ts` land with 3 engine-mod lines merged.
2. ChipSynth plays a 16-bar test track to completion without buffer
   underruns (vitest browser, listen-only or spectral assertion).
3. Sfxr produces 5 canonical archetypes (pickup/laser/explosion/jump/
   hit) in < 100ms each, each generates non-silent audio of expected
   duration.
4. Schema validator catches 3 malformed audio scripts with correct
   error kinds (`unknown_sfx_preset`, `invalid_chiptune_track`,
   `library_ref_not_sfx_library`).
5. End-to-end: Tsunami emits a design script with `ChipMusic` +
   `SfxLibrary` + 3 `play_sfx_ref` actions → the built game plays
   BGM + SFX.

## 9. Falsifier

If procedural audio produces **less distinctive sound** than asset-
based audio (pre-made mp3/wav referenced by id) at the same prompt
set — as judged by visual QA or operator — the procedural path is
adding friction without value. Revert the ActionRef kinds to
`play_sound { asset: string }` only and ship audio assets from a
Tsunami-curated library instead.

## 10. Open questions (for attempt_002 if needed)

1. Should ChipSynth expose a lower-level API for custom waveforms
   (Amiga / SID emulation), or stay at NES-simplicity? Defer until
   demand.
2. Noise-channel drum token mapping — who owns it? Synthesis (code) or
   content (data)? I'll propose the mapping lives in `chipsynth.ts` as
   a fixed table for v1.1; custom drums wait for v1.2.
3. Should `SfxLibrary` presets be pre-rendered at script load or
   on-demand? Pre-render trades memory for latency. Default:
   pre-render (audio graph is async anyway). Content thread may have
   input on typical library size.
4. Does `play_chiptune` require the `ChipMusic` mechanic to be
   instantiated globally, per-scene, or per-call? Recommend: per-
   mechanic-instance, keyed by `id`, lifetime = mechanic lifetime.
5. Spatial chiptune (HRTF-panned ChipMusic for e.g. a radio in
   3D-world)? Deferrable to v1.2.

## 11. Stop-signal check

Structural movement this fire: **YES** — landed concrete types
(`ChipMusicTrack`, `NoteEvent`, `SfxrParams`, new ActionRef kinds, 2
new MechanicTypes), engine-integration deltas (3 methods), 3 validator
error classes, ship criteria, falsifier. Content thread unblocked
from placeholder shapes.

Not a re-state. Continue.

## Handoff note to content thread

Shapes are now concrete:
- **ChipMusicTrack** above is the track JSON shape. Replace your
  placeholder in `library/track_NNN.md`.
- **SfxrParams** above is the sfxr seed shape. Your
  `library/sfx_NNN.md` entries should use this param set.
- **Noise channel** uses named drum tokens (`kick`, `snare`,
  `hat_closed`, `hat_open`, `crash`). Flag me if you need more drums;
  I'll extend the table.

I'll read your `priors/` and `library/` next fire for any cross-thread
signals.
