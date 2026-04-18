# Audio extension — attempt 003

> Synthesis thread, fire 3. Content-thread note: "fire 3 didn't
> surface additional cross-thread signals — priors 011–015 reinforced
> existing patterns." One subtle finding I caught anyway from
> game_013, plus audit of attempt_002. Expect stop-signal within 1–2
> fires.

## Confirmation-bias audit of attempt_002

**Rejection count.** For the dynamic-layer shape (F2), I considered
and rejected:
- N-layer stem mixer (3+ simultaneous layers with per-layer gain).
  Rejected: only 1 corpus example (Mega Man X "upgraded engine")
  warranted >2 layers; schema bloat unjustified. Named this already
  in attempt_002 open questions.
- Per-ActionRef layer control (imperative style: `activate_layer` /
  `deactivate_layer`). Rejected: condition-driven crossfade is
  declarative-cleaner and fits the existing flow-condition idiom.
  2-layer max stays authorable.

**Construction check.** F2's shape was proposed BY content thread in
`priors/game_009.md` (Shovel Knight). I accepted their spec verbatim,
so construction bias on this feature is corrected at source. No
re-work needed.

**Predictive test.** Attempt_002's BPM-reference spec predicts content
should be able to express Tetris GB's tempo ramp. Content fire-3 added
`game_006 Tetris`: "BPM-as-difficulty" is documented, shape fits
(`bpm: { mechanic_ref: 'diff', field: 'tempo_scalar' }`). Prediction
holds.

Audit outcome: attempt_002 stands. No revisions.

## New finding from content priors 011–015

**F4 — Dynamic mixer mutation (subtle; content didn't flag as schema
gap).**

game_013 Zelda ALttP notes: "Our chipsynth can mute/unmute channels
per-track at runtime (via mixer map). Using `mixer` values of 0 for
certain bars lets authors 'pull channels out' for tension drops."

Content stated this as a capability. **But the schema as written at
attempt_002 compiles `mixer` at play-time and doesn't expose runtime
mutation.** The `mixer` field is static `Partial<Record<ChipChannel,
number>>`. An author who wants tension-drop via dynamic channel mute
has no schema path.

Two fixes, consistent with attempt_002 patterns:

**Fix A — mechanic-reference mixer values (preferred, consistent with F1/F2):**

```ts
export interface ChipMusicTrack {
  bpm: number | { mechanic_ref: MechanicId; field: string }
  // ... existing ...
  mixer?: Partial<Record<ChipChannel, number | {
    mechanic_ref: MechanicId;
    field: string;
    ramp_ms?: number            // default 50ms smoothing to avoid pops
  }>>
}
```

Implementation: if a channel's mixer is a ref, the scheduler reads the
ref value each scheduler tick (every 25ms lookahead) and applies
`gain.linearRampToValueAtTime(newValue, ctx.currentTime + rampMs/1000)`.
Ref resolution uses the same mechanism as F1's BPM ref.

Use cases:
- Tension drop: `mixer: { pulse2: { mechanic_ref: 'combat_state', field: 'intensity' }}` — combat mechanic exposes `intensity` 0..1, pulse2 channel follows.
- Dynamic layering's less-heavy cousin: single channel fades instead of whole track overlay.
- HP-threshold de-emphasis: channel fades as HP drops (combined with the alarm loop, music gets sparser).

Cost: ~15 lines in scheduler. Reuses F1's ref-resolution code.

**Fix B (deferred v1.1.2) — imperative ActionRef:**

```ts
// not shipping v1.1:
// | { kind: 'set_chipmusic_channel_gain'; track_ref: MechanicId; channel: ChipChannel; gain: number; ramp_ms?: number }
```

Keeps ActionRef union from bloating. Reference-based is sufficient
for v1.1.

**Decision: ship Fix A in v1.1.** Cost low, consistency high, covers
named corpus cases.

## Net additions for attempt_003

Beyond attempt_002:
1. Mixer channel values can be mechanic refs (F4 Fix A).
2. One validator check: mixer ref's mechanic exposes the named field
   (same error class as `unknown_mechanic_field` from attempt_002 — no
   new error class needed).

Cost: ~15 LOC. Content-side impact: next track JSON they author can
demonstrate ref-mixer; not blocking current library.

## Updated ChipMusicTrack shape (cumulative attempt_001 + _002 + _003)

```ts
export interface ChipMusicTrack {
  bpm: number | MechanicRef            // F1 (attempt_002)
  bars?: number
  loop: boolean
  loopStart?: number
  channels: Partial<Record<ChipChannel, NoteEvent[]>>  // + wave (attempt_002 S2)
  mixer?: Partial<Record<ChipChannel,
    number | (MechanicRef & { ramp_ms?: number })>>  // F4 (this fire)
  wave_table?: number[]                // attempt_002 S2
}

interface MechanicRef {
  mechanic_ref: MechanicId
  field: string
}

export type ChipChannel =
  'pulse1' | 'pulse2' | 'triangle' | 'noise' | 'wave'
```

## Updated ChipMusicParams shape

```ts
export interface ChipMusicParams {
  base_track: ChipMusicTrack
  overlay_track?: ChipMusicTrack        // attempt_002 F2
  overlay_condition?: ConditionKey      // attempt_002 F2
  crossfade_ms?: number                 // attempt_002 F2 (default 500)
  channel: 'music' | 'ambient'
  autoplay_on?: ConditionKey
  stop_on?: ConditionKey
  // Planned v1.1.2:
  // echo?: { ms: number; feedback: number; wet: number }
  // chip_mode?: 'nes' | 'vrc6' | 'vrc7' | 'mmc5' | 'n163' | 'fme7'
}
```

## Updated SfxrParams shape — unchanged from attempt_001

27-param jsfxr-canonical. Content fires 2–3 exercised 10 seeds against
this shape without flagging issues. Shape stable.

## Updated ActionRef union — unchanged from attempt_002

7 audio-related kinds (play_sfx, play_sfx_ref, play_sfx_loop,
play_sfx_loop_ref, stop_sfx_loop, play_chiptune, stop_chiptune).
Content fires 2–3 exercised via library seeds + loop use cases
(engine drone, HP alarm, boss warning, charge hold) without gaps.

## Catalog entries — update for F4

`ChipMusic` entry's `emits_fields` list extends to:
- `is_playing`
- `current_beat`
- `active_layer` (from F2)
- `channel_gain.pulse1`, `.pulse2`, `.triangle`, `.noise`, `.wave`
  (for other mechanics that want to consume this — e.g., audio-
  visualizer mechanic)

`common_patches` gains: `mute channel by mixer→0`,
`reference difficulty for dynamic mixer`.

## Ship criteria — append one test

Previously 8 criteria (1–5 attempt_001, 6–8 attempt_002).

9. (new) Mixer-ref test: ChipMusicTrack with a channel mixer as
   `{mechanic_ref, field}` reads the current value each scheduler
   tick; changing the referenced field within 25ms produces a ramped
   gain change without audible pop.

## Stop-signal projection

Current state:
- Content fire 3: no new cross-thread signals (their explicit note).
- Synthesis fire 3: one subtle signal (F4) caught by re-reading
  priors; not flagged by content. Structural movement YES but smaller
  than fires 1 or 2.
- Next content fire (fire 4): projected to complete 20/12/20 quotas +
  palette_MAP expansion. Content's own plan says: "If Data Ceiling
  hit (consecutive no-signal priors), hold and flag."

**Projected outcome fires 4–5:**
- If content fire 4 surfaces 0 new signals → I audit attempt_003,
  find nothing, attempt_004 becomes a repeat → both hit Data Ceiling.
- If content fire 4 surfaces ≥ 1 signal → attempt_004 incorporates.

I'm below my ship-target of 5 attempts but the 5-attempt target was
budget-speculative, not requirement. **Attempt_003's spec state is
actually implementer-ready** — chipsynth.ts + sfxr.ts + schema deltas
+ validator + prompt scaffold content (when content fire 4 completes).

**Early-ship recommendation:** if no new signal surfaces in fires
4–5, flag operator that attempt_003 is the v1.1 lock-in target and
implementer can start. Don't churn past Data Ceiling.

## Self-check

- Audio scope? ✓
- Re-checked engine.ts? ✓ (in-session since fire 1)
- Zero-dep / web-first / agent-authorable? ✓ (F4 is pure Web Audio
  gain automation)
- Landable in one sitting? ✓ (~15 LOC addition + 1 validator check)
- New structural movement? ✓ (F4 is a real schema gap content didn't
  flag; caught via re-read)

5/5 yes. Continue. Expect slowing pace next 1–2 fires → likely stop.

## Handoff to content thread

- **mixer can reference mechanics** now. If you author a track where
  tension-drop via channel fade is useful, demo it. Example:
  `mixer: { pulse2: { mechanic_ref: 'combat', field: 'intensity' }}`.
- Otherwise, no changes — attempt_002 shapes still canonical.
- Fire 4 plan sounds good (5 priors + 3 tracks + 5 sfx + palette_MAP
  expansion). Go. Flag if any new structural signal surfaces.

## Summary for operator

Three attempts landed:
- **attempt_001:** foundational shapes + ship criteria + falsifier.
- **attempt_002:** 4 accepted content signals + 3 new findings +
  audit.
- **attempt_003:** 1 subtle finding (dynamic mixer mutation) + audit +
  projected stop.

All incremental; no churn; no rewrites. Content thread leads; I
catch gaps they don't name.

v1.1 audio extension is implementer-ready as of attempt_003. Remaining
risk: content fire 4 might surface a signal that matters. If not,
stop-signal follows in 1–2 fires.
