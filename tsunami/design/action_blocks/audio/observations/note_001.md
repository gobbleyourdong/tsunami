# Observation 001 — Six schema / API items from fire-1 content mining

**From:** content thread, fire 1.
**Audience:** synthesis thread (on your next attempt, please consider).
**Source data:** priors/game_001..005, library/track_001..003, library/sfx_001..005.

Six cross-track signals surfaced while writing the first batch.
Listed in rough priority order (high impact on schema first).

## 1. Time / duration in beats, not seconds

**Evidence:** track_001/002/003 all authored with per-note
`time`/`duration` in seconds, computed from BPM. That's brittle — if
a designer or QA wants to adjust a track's tempo (a common mutation
per attempt_008), every note event needs re-arithmetic.

**Recommendation:** in the `ChipMusic` NoteEvent type, make `time`
and `duration` expressed in **beats** (fractional OK), and let the
scheduler resolve beats × BPM → seconds at playback time.

```ts
interface NoteEvent {
  time: number       // beats from track start
  note: string | number  // 'C5' or MIDI number
  duration: number   // beats
  velocity?: number  // 0-1
}
```

Tempo change = single-field mutation instead of regenerating every
event. Big authoring win.

## 2. Drum name mapping for noise channel

**Evidence:** track_002 uses `"note": "kick" / "hat" / "snare"` on
the noise channel. track_003 uses `"crash"`. The chipsynth needs a
mapping table of drum names → noise-generator configurations
(period length, envelope shape).

**Recommendation:** include a built-in `DRUM_PRESETS` table in
chipsynth.ts, keyed by a small vocabulary:

```
kick  → short low-period noise, sharp decay
snare → medium-period noise, medium decay with slight buzz
hat   → short high-period noise, very short decay (hi-hat tick)
crash → long high-period noise, long decay with LPF sweep
tom_hi / tom_lo → medium-period, pitched
```

Alternative: designers author drum sounds as sfxr params, noise
channel accepts either drum-name OR inline sfxr params. Either works;
the name-based path is easier for the LLM to emit.

## 3. Optional 5th channel — "wave" / custom waveform

**Evidence:** priors/game_003 (Link's Awakening / Game Boy). The
wave channel is a 32-sample 4-bit user-defined lookup table that
functions as a 5th timbral slot. Games swap its table mid-song to
change instrument color. Kirby's Dream Land, Zelda LA, DKC GBC —
all rely on the wave channel.

**Recommendation:** consider a 5th optional channel `wave` in the
`ChipMusic.channels` shape:

```ts
channels: {
  pulse1?: NoteEvent[]
  pulse2?: NoteEvent[]
  triangle?: NoteEvent[]
  noise?: NoteEvent[]
  wave?: NoteEvent[]       // NEW — uses a user-supplied waveform table
}
wave_table?: number[]      // 32 samples, each in 0..15 (4-bit), at mechanic level
```

Web Audio implementation: `PeriodicWave` from `ctx.createPeriodicWave`
takes real/imaginary arrays — same shape as a custom waveform table.
Implementation cost is small (~20 lines).

Scope judgment: if this adds >1 day of synth work, defer. If it's
half a day, the priors suggest it's high-leverage.

## 4. Pitch-slide (portamento) as per-note parameter

**Evidence:** priors/game_003 (Link's Awakening, GB Pulse 1 hardware
sweep). A signature "fill" sound in GB soundtracks is a pitch slide
from one note to another over a fraction of a beat. The hardware
did it natively; we'd need a per-note `slide_from` or `slide_to`
parameter on NoteEvent.

**Recommendation:** low priority for v1 (can be faked by chaining
many short notes at incremented pitches), but name-tag it for v1.1:

```ts
interface NoteEvent {
  ...
  slide_from?: string | number   // optional — start pitch, slide to 'note' over 'slide_ms'
  slide_ms?: number
}
```

Chipsynth implementation: use `oscillator.frequency.setTargetAtTime`
or `linearRampToValueAtTime` — already in Web Audio API.

## 5. Echo as a post-FX bus

**Evidence:** priors/game_002 (Chrono Trigger's S-DSP hardware echo).
Many SNES tracks rely on a shared echo bus for "space" — small
implementation (one delay line + feedback), big feel gain.

**Recommendation:** optional `EchoParams` on the `ChipMusic`
mechanic or on individual channels:

```ts
{ echo_ms?: number, echo_feedback?: number, echo_wet?: number }
```

Web Audio: `DelayNode` + `GainNode` feedback loop; trivial to add.
Out-of-scope for v1 if the shape is tight, but flag for v1.1.

## 6. `play_sfx_loop` / `stop_sfx_loop` as separate ActionRefs

**Evidence:** priors/game_005 (Pac-Man). Pac-Man's power-pellet siren
and hurry-up alarm are state-sonification loops, not one-shots. The
`play_sfx` ActionRef as currently specified in BRIEF.md is a one-
shot — no way to trigger a looping SFX that stops on a state change.

**Recommendation:** add to the schema diff you're planning:

```ts
| { kind: 'play_sfx';       params: SfxrParams }           // one-shot
| { kind: 'play_sfx_loop';  id: string; params: SfxrParams }   // NEW
| { kind: 'stop_sfx_loop';  id: string }                        // NEW
```

`id` is the player's handle for later stopping. Looping SFX as a
first-class concept also benefits survival-horror (heartbeat, alarm)
and racing (engine drone).

---

**Summary of recommendations to synthesis thread:**
1. (high impact) Time/duration in beats, not seconds
2. (high impact) Drum-name mapping table
3. (moderate) Optional 5th "wave" channel
4. (low, v1.1) Pitch-slide per-note
5. (low, v1.1) Echo post-FX
6. (moderate) Looping SFX ActionRefs

None of these are blockers on my side — I'll continue authoring against
the placeholder shape from BRIEF_CONTENT.md. If the final schema
differs, track/sfx files may need a shape-migration pass; that's a
mechanical refactor, not a re-author.

Will write note_002 next fire if more cross-track signals surface.
