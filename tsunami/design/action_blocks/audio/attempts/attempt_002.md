# Audio extension — attempt 002

> Synthesis thread, fire 2. Audit of attempt_001 + incorporate 4
> accepted signals from content note_001 + 3 new findings from content
> priors 006–010.

## Confirmation-bias audit of attempt_001

Per Sigma v7 protocol.

**Rejection count.** I didn't enumerate alternative authoring surfaces I
rejected. Candidates I had in mind but didn't document:
- **MML strings** (`"T120 O4 L4 cdefga b"`) — PC-98 / AY-3-8910 classic.
  Terse, LLM-emittable, long track record. Rejected: harder to validate
  statically, harder to apply JSON Patch mutations for QA feedback loop.
- **Tracker row format** (Impulse Tracker `C-4 01 .. ..`) — authentic to
  the medium. Rejected: dense, error-prone, the LLM would emit it as
  strings not structured data.
- **MIDI-like delta-time events** — `{delta_ticks, event_kind, ...}`.
  Rejected: delta-based authoring doesn't survive JSON diff patches
  well; beat-anchored absolute time is more mutation-friendly.

Named now; kept structured-JSON per original reasoning.

**Construction check.** The 3 example tracks I sketched were constructed
to fit my shapes. Content thread's independent authoring (tracks
001–006) was the real stress-test. Their note_001 surfaced 6 gaps —
construction bias partially corrected. Audit outcome: fit-to-shape
bias was real, content thread corrected it via independent use.

**Predictive test.** attempt_001 predicts which games fall out of v1.1
scope: Genesis FM, SNES ADPCM, Amiga MOD. Content priors confirmed:
- game_002 Chrono Trigger SNES ADPCM → flagged "partial scope"
- game_004 Sonic 2 YM2612 FM → flagged "out of chipsynth scope"
- NES/GB/arcade WSG all fit within 4-channel model → all expressible.

Predictions held. Good.

## 4 accepted signals from content note_001 — landing

### S1 — Extended drum vocabulary (7 tokens)

`ChipSynth` noise-channel drum tokens lock at:

```
kick         — low period, sharp decay
snare        — medium period, medium decay, slight buzz
hat          — alias for hat_closed
hat_closed   — short high period, very short decay
hat_open     — short high period, longer decay with LPF sweep
crash        — long high period, long decay with LPF sweep
tom_hi       — medium period, pitched high
tom_lo       — medium period, pitched low
```

Implementation: `DRUM_PRESETS: Record<string, NoiseConfig>` table in
`chipsynth.ts`. `NoiseConfig = { periodLength: number; envelope:
EnvelopeADSR; lpSweep?: {from: number; to: number; ms: number} }`.

Cost: ~25 lines. Eight entries (7 canonical + alias).

### S2 — Optional 5th `wave` channel

`ChipMusicTrack` extended:

```ts
export interface ChipMusicTrack {
  bpm: number | MechanicId          // see S5 below — static or ref
  bars?: number
  loop: boolean
  loopStart?: number
  channels: Partial<Record<ChipChannel, NoteEvent[]>>
  mixer?: Partial<Record<ChipChannel, number>>
  wave_table?: number[]             // NEW: 32 samples, each 0..15 (4-bit)
}

export type ChipChannel = 'pulse1' | 'pulse2' | 'triangle' | 'noise' | 'wave'
```

Implementation: when `wave` channel is used, `chipsynth.ts` constructs a
`PeriodicWave` from `wave_table` via
`ctx.createPeriodicWave(real, imag)` where arrays are derived from the
32-sample table. Oscillator uses the custom wave; envelope applies
normally.

Cost: ~20 lines (as content thread predicted). Triggers test case: GB
wave channel tracks (game_003 Link's Awakening, game_006 Kirby when
added).

### S3 — Loop SFX ActionRefs

`ActionRef` union further expanded:

```ts
| { kind: 'play_sfx';       params: SfxrParams }                 // one-shot
| { kind: 'play_sfx_ref';   library_ref: MechanicId; preset: string }
| { kind: 'play_sfx_loop';  id: string; params: SfxrParams }     // NEW
| { kind: 'play_sfx_loop_ref'; id: string; library_ref: MechanicId; preset: string }  // NEW
| { kind: 'stop_sfx_loop';  id: string }                         // NEW
| { kind: 'play_chiptune';  track_ref: MechanicId }
| { kind: 'stop_chiptune';  track_ref: MechanicId; release_tail?: boolean }
```

`id` is author-chosen handle for later stop. Two-variant loop
(inline params + library ref) mirrors one-shot convention.

Cost: ~15 lines of handle-tracking in `AudioEngine` (reuse
`activeSources` map, keyed by handle).

### S4 — Mark pitch-slide + echo as v1.1.2 in types

Add TS doc-comments on `NoteEvent` and `ChipMusicParams`:

```ts
export interface NoteEvent {
  time: number
  note: string
  duration: number
  velocity?: number
  envelope?: EnvelopeADSR
  dutyCycle?: number
  vibrato?: { rate: number; depth: number }
  // Planned v1.1.2:
  // slide_from?: string;  slide_ms?: number   // portamento
}

export interface ChipMusicParams {
  // ... existing ...
  // Planned v1.1.2:
  // echo?: { ms: number; feedback: number; wet: number }
}
```

Zero runtime cost; documents intent so v1.1.2 refactor has a
placeholder.

## 3 new findings from content priors 006–010

### F1 — BPM modulation (Tetris GB pattern, game_006)

Tetris's difficulty ramp is expressed mechanically as BPM increase.
Currently my schema has `bpm: number` static. Let it reference a
mechanic's exposed field:

```ts
export interface ChipMusicTrack {
  bpm: number | { mechanic_ref: MechanicId; field: string }
  // ...
}
```

Example usage:
```json
{
  "bpm": { "mechanic_ref": "diff", "field": "tempo_mul_base_120" },
  "loop": true,
  "channels": { ... }
}
```

The `Difficulty` mechanic's existing S-curve output multiplies a base
BPM (120 × curve = 60..240). Lives within existing `exposes_fields`
contract. Scheduler reads the ref each loop cycle.

Cost: ~15 lines in `chipsynth.ts` scheduler + 1 new validator error
class (`unknown_mechanic_field`).

### F2 — Dynamic-layer crossfade (Shovel Knight / game_009)

Content thread proposed concrete shape:

```ts
export interface ChipMusicParams {
  base_track: ChipMusicTrack
  overlay_track?: ChipMusicTrack
  overlay_condition?: ConditionKey    // fade in when set
  crossfade_ms?: number               // default 500ms
  // ... existing fields ...
}
```

Two `ChipSynth` instances, mixed via a shared `GainNode` crossfade.
Existing `AudioEngine.playMusic` already has crossfade logic — rotate
it into a reusable utility.

**Decision: include in v1.1.** Cost ~30 LOC. High-leverage per
content's 3-game corroboration (Shovel Knight + Mega Man 2 combat
escalation + SF2 life-low heartbeat-layer). This is the kind of
"small mechanic × composition = signature feel" that note_007
names — exactly the composability we want.

### F3 — Expansion-chip channels (Castlevania III VRC6, game_010)

Content thread flags as v1.1 stretch. I concur — **defer to v1.1.2**.

Rationale: adds +3 channels (pulse3, pulse4, saw) behind a `chip_mode:
'vrc6' | 'vrc7' | 'mmc5' | 'n163' | 'fme7' | 'nes'` flag. Default
`'nes'` = current 4ch + optional wave = 5ch max. Each expansion chip is
its own PeriodicWave setup. High surface area, marginal audience. Land
after v1.1.1.

Mark in schema as v1.1.2 placeholder:

```ts
export interface ChipMusicParams {
  // ... existing ...
  // Planned v1.1.2:
  // chip_mode?: 'nes' | 'vrc6' | 'vrc7' | 'mmc5' | 'n163' | 'fme7'
}
```

## Updated catalog entries

```ts
ChipMusic: {
  type: 'ChipMusic',
  description:
    '4-channel chiptune (2 pulse + triangle + noise, optional 5th wave) ' +
    'with optional overlay-crossfade layer. BPM can be static or reference a Difficulty mechanic.',
  example_params: {
    base_track: {
      bpm: 120,
      loop: true,
      channels: {
        pulse1: [{ time: 0, note: 'C5', duration: 0.5 }, /* ... */],
        triangle: [{ time: 0, note: 'C3', duration: 1.0 }, /* ... */],
      },
    },
    overlay_track: { /* combat-intensity percussion + counter-melody */ },
    overlay_condition: 'combat_active',
    crossfade_ms: 500,
    channel: 'music',
  },
  emits_fields: ['is_playing', 'current_beat', 'active_layer'],
  common_patches: ['swap base_track', 'toggle overlay', 'adjust crossfade_ms'],
},
```

`SfxLibrary` unchanged from attempt_001.

## Validator additions (attempt_002 delta)

New error class beyond the 3 in attempt_001:

- `unknown_mechanic_field`: `ChipMusicTrack.bpm.field` not in referenced
  mechanic's `emits_fields`.

Cost: +1 error class. Validator validates ref chain at compile time.

## Ship criteria (updated)

Unchanged from attempt_001 except:

6. (new) Overlay-crossfade test: ChipMusic with overlay_track plays
   base alone, then base+overlay after condition fires, with correct
   crossfade timing.
7. (new) Wave channel test: ChipMusicTrack with wave_table + wave
   channel events produces expected periodic output.
8. (new) BPM-reference test: `bpm: {mechanic_ref, field}` reads from
   Difficulty mechanic's exposed field; BPM change reflects at next
   loop cycle.

## Open questions deferred to attempt_003 if needed

From attempt_001: all 5 closed at attempt_002 except #2 (drum token
extensibility) — now somewhat-answered with 7-token canonical + alias
but content might push more tokens as corpus grows.

New open questions:
- Should BPM-reference also support a `multiplier` param (`tempo_mul:
  0.5..2.0`) so the difficulty S-curve directly drives tempo without
  needing a dedicated tempo field? Trivially adds `{mul: number,
  mechanic_ref: MechanicId}`. Hold until attempt_003.
- Dynamic-layer shape: should N-layer crossfade be supported (3+
  layers) or is 2 enough? Mega Man X "upgraded engine" has 3-4 layers
  in some tracks. If N-layer, schema grows significantly. Flag for
  later.

## Stop-signal check

Structural movement this fire: **YES**:
- 4 signals accepted with concrete implementations
- 3 new findings from content priors, 2 incorporated + 1 deferred
  with rationale
- Confirmation-bias audit of attempt_001 completed
- Wave channel + loop SFX + dynamic-layer crossfade + BPM-reference
  are all fresh schema additions

Not re-stating. Continue.

## Handoff to content thread

Changes that affect you:
- **Drum vocab locked** at 7 tokens + `hat` alias. No other tokens
  valid until attempt_003 unless you flag a need.
- **`bpm` in ChipMusicTrack can now be a mechanic reference** — worth
  showcasing in at least one new track JSON (Tetris-like ramp).
- **ChipMusic mechanic now has overlay + crossfade** — worth one
  example track with two layers (base + overlay) to validate authoring
  ergonomics from your side.
- **Loop SFX ActionRefs exist** — Pac-Man siren (game_005) is now
  expressible. You can author a looping SFX entry in `library/` with
  `play_sfx_loop` usage notes.
- **Sfx seeds 001–005** still need mechanical re-cast to 27-param
  camelCase form. Low priority; at ship.

My fire-3 plan:
- Read content priors 011–015 + any new observations.
- Audit attempt_002 for bias.
- Iterate only if content surfaces new structural signal or if
  programmer-side implementer flags ambiguity.
- Otherwise hold toward Data Ceiling.
