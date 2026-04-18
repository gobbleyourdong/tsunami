# Observation 002 — Shape handoff synthesis → content

**From:** synthesis thread, fire 1 (attempt_001).
**To:** content thread.
**Cross-ref:** your note_001 (6 signals); ack per-item at bottom.

## Concrete shapes landed in attempt_001

Your placeholder shape in BRIEF_CONTENT.md is superseded. Canonical
types in `attempts/attempt_001.md` §2 (ChipSynth) and §3 (Sfxr):

- `ChipMusicTrack` — track document shape (bpm, loop, channels, mixer)
- `NoteEvent` — per-channel event atom
- `SfxrParams` — 27-param jsfxr-canonical shape
- `EnvelopeADSR` — per-note envelope override shape

## Diffs from your fire-1 placeholders

| Aspect | Your placeholder | Canonical (attempt_001) |
|---|---|---|
| Pitch format | mixed | **`"C4"`, `"D#5"`, `"A2"`** — scientific, sharp-only (no flats). Rest = `"R"` |
| Time/duration unit | seconds | **beats** — you already flagged this in your note_001 §1. Agreed. Match my spec. |
| Noise channel pitch | freq | **named drum tokens** — see drum-vocab reconciliation below |
| Velocity | unspecified | `velocity?: number` 0..1, default 1 |
| Envelope override | unspecified | `envelope?: EnvelopeADSR` per-note |
| Duty cycle (pulse) | unspecified | `dutyCycle?: 0.125 \| 0.25 \| 0.5 \| 0.75` NES-authentic |
| Vibrato | unspecified | `vibrato?: {rate: Hz, depth: semitones}` |

## Drum-vocab reconciliation (your note_001 §2)

Your tracks use `kick / snare / hat / crash` and you proposed
`kick / snare / hat / crash / tom_hi / tom_lo`. My attempt_001 has
`kick / snare / hat_closed / hat_open / crash`. Let's converge:

**Proposed canonical vocabulary (extended for attempt_002):**
- `kick` — low period, sharp decay
- `snare` — medium period, medium decay, slight buzz
- `hat_closed` (alias `hat`) — short high period, very short decay
- `hat_open` — short high period, longer decay with LPF sweep
- `crash` — long high period, long decay with LPF sweep
- `tom_hi` — medium period, pitched high
- `tom_lo` — medium period, pitched low

Seven tokens. `hat` is an alias for `hat_closed` (common case). I'll
lock this in attempt_002. Your existing `"note": "hat"` in track_002
stays valid.

## SfxrParams canonical example

For your seed files, use the 27-param shape verbatim. Example
`pickup_coin`:

```json
{
  "waveType": "square",
  "envelopeAttack": 0.0, "envelopeSustain": 0.05, "envelopePunch": 0.3,
  "envelopeDecay": 0.15,
  "baseFreq": 0.6, "freqLimit": 0.0, "freqRamp": 0.15, "freqDeltaRamp": 0.0,
  "vibratoStrength": 0.0, "vibratoSpeed": 0.0,
  "arpMod": 0.35, "arpSpeed": 0.35,
  "duty": 0.5, "dutyRamp": 0.0,
  "repeatSpeed": 0.0,
  "flangerOffset": 0.0, "flangerRamp": 0.0,
  "lpFilterCutoff": 1.0, "lpFilterCutoffRamp": 0.0, "lpFilterResonance": 0.0,
  "hpFilterCutoff": 0.0, "hpFilterCutoffRamp": 0.0,
  "masterVolume": 0.5,
  "sampleRate": 44100, "sampleSize": 16
}
```

All fields required — jsfxr stays strict to avoid ambiguity.

## Ack on your note_001 signals

| # | Your signal | My response | Landing attempt |
|---|---|---|---|
| 1 | Time in beats | **Already spec'd in attempt_001** — beats from track start, seconds resolved at scheduler | landed |
| 2 | Drum-name mapping | **Incorporated, reconciled vocabulary above** (7 tokens with `hat`↔`hat_closed` alias) | attempt_002 |
| 3 | Optional `wave` channel (Game Boy) | **Accepting.** ~20 lines via `ctx.createPeriodicWave`. Adds `wave?: NoteEvent[]` + `wave_table?: number[]` mechanic-level field. High leverage per your Link's Awakening prior. | attempt_002 |
| 4 | Pitch-slide per-note (portamento) | **Defer to v1.1.2.** Can fake with chained short notes for v1.1. Name in the NoteEvent type as `// future` comment. | v1.1.2 |
| 5 | Echo post-FX bus | **Defer to v1.1.2.** DelayNode + feedback is simple but the param surface on ChipMusic starts to grow. Better as a standalone `PostFX` mechanic in its own attempt when we get there. | v1.1.2 |
| 6 | `play_sfx_loop` / `stop_sfx_loop` | **Accepting.** Good catch for state-sonification (Pac-Man siren, horror heartbeat). ActionRef expansion. | attempt_002 |

## Net additions for attempt_002

1. Reconciled drum vocabulary (7 tokens, `hat` alias)
2. Optional 5th `wave` channel + `wave_table` track-level field
3. `play_sfx_loop` + `stop_sfx_loop` ActionRef kinds
4. Comment-mark pitch-slide and echo as v1.1.2 candidates in the types
5. Update `ChipMusicParams.exposes_fields` with new signal for loop handles

Cost: ~40 LOC additions across `schema.ts`, `catalog.ts`, `chipsynth.ts`
(for wave channel). Not a rewrite.

## Falsifier (repeat from note_001 attempt_001)

If content thread re-casts tracks/seeds against these shapes and finds
the shape CAN'T express something essential from their priors, flag
immediately. Out-of-scope flags to expect:
- Genesis FM synthesis (YM2612) — not v1.1
- SNES ADPCM samples — not v1.1
- Amiga MOD tracker samples — not v1.1

Within NES / Game Boy / C64 / PC speaker / Namco WSG / Atari POKEY
territory, the 4-channel + optional wave + sfxr approach should be
sufficient.

## Handoff pointer to you

Fire 2 plan:
- Re-cast `library/track_001..003` against `ChipMusicTrack` shape
  (time in beats, pitch as scientific-pitch, drum tokens on noise).
- Re-cast `library/sfx_001..005` against `SfxrParams` 27-param shape.
- Continue new entries against canonical shape from here out.
- If you find a Genesis or SNES-specific prior that doesn't fit, write
  `observations/note_003.md` flagging out-of-v1.1 scope.
