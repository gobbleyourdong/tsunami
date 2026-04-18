# Audio extension — attempt 004

> Synthesis thread, fire 4. Content-thread status: quotas complete
> (20/12/20 + palette_MAP), on standby. Status said "no new
> observations fire 3," but priors 018/019 (Rez + NecroDancer) contain
> v1.1.3-tagged signals I missed in fire 3. Correcting.

## Audit of attempt_003

**Rejection count.** For F4 (dynamic mixer), I rejected imperative
`set_chipmusic_channel_gain` ActionRef in favor of ref-based mixer
values. Rationale stands: consistency with F1/F2 patterns, no union
bloat. Named.

**Construction check.** F4 shape was derived from one content prior
(game_013 Zelda ALttP) and generalized. Not overly fitted; applies
cleanly to the tension-drop use case and to the combined "HP-alarm +
music-sparsens" pattern. OK.

**Predictive test.** attempt_003's mixer-ref spec should cover
content's remaining dynamic-audio cases. Fire 4 stress-test below
(game_018/019) reveals shapes it DOESN'T cover — see §1.

**Audit outcome:** attempt_003 stands for what it addresses, but it's
incomplete against the rhythm-action sub-genre that priors 018/019
documented. Attempt_004 fills the gap.

## Self-audit: I missed signals in fire 3

Priors 018 (Rez) and 019 (NecroDancer) — both landed in content fire 3
and both contained "Lessons for action-blocks audio" sections flagging
v1.1.3 candidates. I read game_013 only. Content's status correctly
said "no new observations" because they didn't write a formal
`note_NNN.md`; the signals were IN the priors themselves.

**Lesson:** "Priors Don't Beat Source" applies to cross-thread reads
too. Content thread's priors ARE source; reading the status summary
isn't the same as reading the prior. Fire-4+ discipline: read new
priors directly, not just status recaps.

Net effect: these signals are 1 fire delayed. Not critical — fire 4
incorporates them. Flagged for future self.

## 3 new findings from priors 018–019

### F5 — Beat-quantized SFX firing (Rez, NecroDancer)

**Source:** game_018 Rez — every player action beat-quantized; game_019
NecroDancer — rhythm-gated action.

**Finding:** ActionRef dispatch is immediate. No way for an author to
say "fire this SFX aligned to the next beat of the current ChipMusic."

**Fix:** add optional `quantize_to` field on audio ActionRef kinds:

```ts
type QuantizeGrid = 'none' | 'beat' | 'half' | 'bar'

// ActionRef additions (all audio-playing kinds):
| { kind: 'play_sfx';          params: SfxrParams;                       quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
| { kind: 'play_sfx_ref';      library_ref: MechanicId; preset: string;  quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
| { kind: 'play_sfx_loop';     id: string; params: SfxrParams;           quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
| { kind: 'play_sfx_loop_ref'; id: string; library_ref: MechanicId; preset: string; quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
// stop_sfx_loop, play_chiptune, stop_chiptune don't need quantize
```

Default: `quantize_to: 'none'` = fire immediately (current behavior).
`quantize_source` defaults to the first ChipMusic mechanic in the design;
authors can target a specific one if multiple are present.

**Implementation:** at ActionRef dispatch, if `quantize_to !== 'none'`:
compute `next_grid_time = ctx.currentTime + (beats_until_grid / bpm * 60)`
and schedule `sfx.start(next_grid_time)` instead of immediate. All
Web Audio API native.

**Cost:** ~20 LOC in the ActionRef dispatcher. No new union kinds.

**Validator:** if `quantize_source` references a non-existent or
non-ChipMusic mechanic, error `invalid_quantize_source` (new error
class).

**Decision:** ship in v1.1. Small, high-value, unlocks rhythm-action
composition patterns.

### F6 — `on_beat` / `off_beat` as first-class ConditionKeys

**Source:** game_019 NecroDancer — movement gated on beat timing.
`trigger: { kind: 'damage', requires_beat?: 'on' | 'off' }` was
flagged.

**Finding:** ChipMusic exposes `current_beat` (float counter) but
rhythm-gated mechanics need discrete events: "is the player's input
on-beat or off-beat right now?" A float doesn't answer that.

**Fix:** ChipMusic emits two additional fields + a tolerance param:

```ts
export interface ChipMusicParams {
  // ... existing ...
  beat_tolerance_ms?: number   // default 100ms; window around beat
                                // where on_beat is true
}

// ChipMusic emits_fields now includes:
// 'is_playing', 'current_beat', 'active_layer', 'on_beat', 'off_beat',
// 'channel_gain.<channel>'
```

`on_beat` = boolean, true when `|ctx.currentTime - nearest_beat_time|
< beat_tolerance_ms / 1000`. `off_beat` = `!on_beat`. Both resolvable
as ConditionKey by the existing condition resolver (refs of the form
`mechanic_id.field_name`).

Rhythm-gated mechanic example (author-facing):
```json
{
  "id": "bash",
  "type": "DirectionalContact",
  "params": {
    "contact_kind": "damage",
    "requires_condition": "music.on_beat"
  }
}
```

The `DirectionalContact` mechanic doesn't need schema changes — it
already accepts `requires_condition`. Just the ChipMusic emits change.

**Cost:** ~15 LOC in ChipSynth scheduler. Emits 2 new boolean fields
derived from `current_beat`.

**Validator:** cond refs `music.on_beat` / `music.off_beat` resolve if
the mechanic is ChipMusic. No new error class.

**Decision:** ship in v1.1. Unlocks rhythm-gated action genre without
a new scaffold mode.

### F7 — N-layer overlay crossfade (Rez layered-reveal)

**Source:** game_018 Rez — 4–8 layers accumulate based on progress.

**Finding:** attempt_002 F2 spec'd 2-layer (base + overlay). Rez-class
games want 3–8 parallel layers fading in on different conditions.

**Fix:** generalize overlay from single to array:

```ts
export interface ChipMusicParams {
  base_track: ChipMusicTrack
  overlay_tracks?: ChipMusicTrack[]           // was overlay_track: ChipMusicTrack
  overlay_conditions?: ConditionKey[]          // was overlay_condition: ConditionKey
  crossfade_ms?: number
  // ...
}
```

Parallel arrays; `overlay_tracks[i]` fades in when
`overlay_conditions[i]` fires. Author can author 1–8 layers.

**Migration:** attempt_002's `overlay_track` / `overlay_condition` were
singular; refactor to arrays. Content thread's fire 1 didn't use
overlay in any track, so no live content breaks. I'll note this in
handoff.

**Cost:** ~15 LOC in ChipSynth — loop over overlays instead of single.
AudioEngine crossfade utility re-used per overlay.

**Validator:** `overlay_tracks.length === overlay_conditions.length`
required. If mismatched, error `overlay_condition_mismatch` (new error
class).

**Decision:** ship in v1.1. Matches content's Rez spec; minor cost.

## Cumulative shapes (attempt_001 + _002 + _003 + _004)

```ts
export interface ChipMusicParams {
  base_track: ChipMusicTrack
  overlay_tracks?: ChipMusicTrack[]            // F7 (was singular)
  overlay_conditions?: ConditionKey[]          // F7
  crossfade_ms?: number
  beat_tolerance_ms?: number                   // F6 (default 100)
  channel: 'music' | 'ambient'
  autoplay_on?: ConditionKey
  stop_on?: ConditionKey
  // Planned v1.1.2:
  // echo?: { ms: number; feedback: number; wet: number }
  // chip_mode?: 'nes' | 'vrc6' | 'vrc7' | 'mmc5' | 'n163' | 'fme7'
}

// Fields ChipMusic exposes (readable by HUD, triggers, other mechanics):
// - is_playing (boolean)
// - current_beat (number, float)
// - active_layer (number, index of topmost overlay or -1 for base)
// - on_beat (boolean, F6)
// - off_beat (boolean, F6)
// - channel_gain.<channel> (number, per-channel current gain)
```

ActionRef union (audio kinds, cumulative, with F5 additions on first
4):

```ts
| { kind: 'play_sfx';          params: SfxrParams;                            quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
| { kind: 'play_sfx_ref';      library_ref: MechanicId; preset: string;       quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
| { kind: 'play_sfx_loop';     id: string; params: SfxrParams;                quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
| { kind: 'play_sfx_loop_ref'; id: string; library_ref: MechanicId; preset: string; quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
| { kind: 'stop_sfx_loop';     id: string }
| { kind: 'play_chiptune';     track_ref: MechanicId }
| { kind: 'stop_chiptune';     track_ref: MechanicId; release_tail?: boolean }

type QuantizeGrid = 'none' | 'beat' | 'half' | 'bar'
```

Validator error classes (cumulative):

1. `unknown_sfx_preset` (attempt_001)
2. `invalid_chiptune_track` (attempt_001)
3. `library_ref_not_sfx_library` (attempt_001)
4. `unknown_mechanic_field` (attempt_002)
5. `invalid_quantize_source` (F5, this fire)
6. `overlay_condition_mismatch` (F7, this fire)

## Ship criteria (cumulative updates)

1–5 from attempt_001, 6–8 from attempt_002, 9 from attempt_003,
10–12 new this fire:

10. **Quantize test:** `play_sfx` with `quantize_to: 'beat'` fires
    exactly on the next beat of the referenced ChipMusic, not
    immediately. Tolerance ±5ms measured via offline rendering.
11. **on_beat condition test:** rhythm-gated trigger (`requires_condition:
    'music.on_beat'`) fires only within `beat_tolerance_ms` of a beat.
12. **N-layer crossfade test:** ChipMusic with 3 overlay_tracks fades in
    layers 1/2/3 as conditions 1/2/3 fire; each layer fades out when
    its condition clears; crossfade_ms honored.

## Stop-signal projection (updated)

**Fire 4 outcome:** 3 structural additions, all from content priors I
read this fire (not fire 3). Structural movement: YES.

**Fire 5 outlook:** no new content work queued (content on standby).
If synthesis fire 5 produces nothing new after:
- auditing attempt_004
- re-reading priors 016, 017, 020 that I haven't deeply scanned
- Checking the palette_MAP for schema implications

...then Data Ceiling is real and I flag hold.

**Current read:** I've been missing signals in priors by skimming
status. Reading full priors 016, 017, 020 next fire is prudent before
declaring stop.

## Tentative final state of v1.1 audio (if fire 5 audit is clean)

- **`chipsynth.ts`** (~250 LOC now, was ~200) — 4 channels + wave +
  DRUM_PRESETS + scheduler with bpm-ref + mixer-refs + beat-quantize
  dispatch hook + on_beat/off_beat emitters.
- **`sfxr.ts`** (~300 LOC) — 27-param jsfxr port.
- **3 engine integration methods** on AudioEngine.
- **7 ActionRef kinds** with optional `quantize_to` on 4 of them.
- **2 MechanicTypes** (`ChipMusic`, `SfxLibrary`) with expanded exposes
  + overlay_tracks array + beat_tolerance param.
- **6 validator error classes** for the audio surface.
- **Prompt-scaffold** integration pending content's palette_MAP
  migration.

Implementer can start at this state; fire 5 audit might add a couple
small fields but unlikely to be structural.

## Self-check

- Audio scope? ✓
- Re-checked engine.ts? ✓ (in-session cache; confirmed playback-only)
- Zero-dep / web-first / agent-authorable? ✓ (quantize is ctx.currentTime
  scheduling; on_beat is derived from existing current_beat; N-layer is
  iteration)
- Landable in one sitting? ✓ per 3-finding cost estimates (~50 LOC
  aggregate)
- New structural movement? ✓ 3 additions + fixed a self-audit gap
  (priors-over-status read discipline)

5/5 yes. Continue. Expect fire 5 to probe priors 016, 017, 020 then
likely stop.

## Handoff to content thread

- **overlay_track → overlay_tracks[]** migration is a rename. If you
  revisit content with dynamic layers in mind, new tracks should use
  the array form.
- **Rhythm-action palette row** in palette_MAP is a good add now that
  beat-quantize + on_beat are shipping. You flagged this in game_018.
  Worth authoring one palette row for rhythm-action.
- **NecroDancer rhythm-roguelite palette row** similar — game_019
  flagged.
- If you write new observations, write them as `observations/note_NNN.md`
  even for items embedded in priors — so future synthesis fires don't
  miss signals that live in prior "Lessons" sections. My fire 3 skipped
  these.
