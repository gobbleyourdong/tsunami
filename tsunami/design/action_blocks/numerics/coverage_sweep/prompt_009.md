# Prompt 009 — Guitar Hero-style rhythm action

**Pitch:** notes scroll down a track toward a trigger line; hit buttons in time with music; miss → score penalty; build streak for multiplier; song ends → final score.

**Verdict:** **expressible with caveats (closest clean fit so far)**

**Proposed design (sketch):**
- archetypes: `note_lane_1` / `2` / `3` / `4` / `5`, `trigger_zone`
- mechanics: `RhythmTrack` (in v0 — now exercised), `ComboAttacks` (for streak scoring), `ScoreCombos` (combo multiplier), `HUD` (score + streak), `WinOnCount` (song complete)

**Missing from v0:**
- `RhythmTrack` catalog entry wasn't concretized. Needs params: `audio_ref`, `beatmap: [{time_sec, lane, type}]`, `trigger_window_ms`, `hit_action`, `miss_action`.
- **Audio timestamp sync** — notes spawn based on audio playback time, not `scene.elapsed`. Needs `audio.currentTime` anchor. The engine has `AudioEngine` but the mechanic spec doesn't bind to it.
- **Scrolling spawn path** — notes travel from spawn point to trigger zone along a fixed path. This is a parameterized path spawner, not the random-arena-spawn of WaveSpawner.
- **Streak semantics** — break on any miss, persist across notes. `ScoreCombos` is window-based (`window_sec`); rhythm streak is event-based.
- **Visual beat indicator** — beat-flash UI, common in the genre. Not strictly essential but absence is felt.

**Forced workarounds:**
- Hand-author the beatmap JSON inline in the design script — verbose but works. An import-from-file would be better but still expressible.
- Use `ComboAttacks` as streak counter — wrong primitive; it's input-pattern-matching, not hit-streak.

**v1 candidates raised:**
- Concretize `RhythmTrack` spec in the catalog (params + exposed fields)
- `Streak` component (event-counter that resets on failure event, distinct from `ScoreCombos`)
- `ScrollingSpawner` mechanic — directional path spawner (vs. WaveSpawner's arena spawner)
- Audio-time anchor for mechanic ticks

**Stall note:** rhythm is the first genre where v0 has a dedicated-ish mechanic. Exercising it surfaced that the mechanic was named but never fleshed out. A pattern for the design instance: every v0 mechanic needs a full param spec + exposed-field list before it's implementable.
