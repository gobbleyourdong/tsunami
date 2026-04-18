# Palette map — genre × audio

> Mapping from action-blocks target genres to characteristic audio
> palettes. Draws on 15 priors (`priors/game_*.md`) + 15 sfx seeds +
> 9 example tracks.
>
> How to read: for a given genre, use the listed tracks as nearest-
> match starting point, the listed sfx seeds as the core library, and
> the channel-emphasis + mood notes to tune.

## Methodology

Each row reports:
- **Genre** — action-blocks in-scope target (see `action_blocks/
  reference/catalog.ts` OUT_OF_SCOPE_V1 table for excluded genres).
- **Channel emphasis** — which chipsynth channels dominate. Pattern:
  `p1 lead | p2 harmony | tri bass | noise perc | wave flex`.
- **Recommended sfx seeds** — primary archetypes this genre uses.
  Draws from the 15 catalogued seeds (sfx_001..015).
- **Recommended music mood** — closest track in the library (track_001..009).
- **Canonical refs** — 1-2 games from the 15 priors that exemplify.

---

## Palette table

### Arcade shooter (vertical / horizontal shmup)
- **Channel emphasis:** noise-heavy drums + fast p1 lead + driving
  tri bass. p2 often syncopated harmony. wave rare.
- **Recommended sfx:** `laser_small` (sfx_002) + `missile` (sfx_013)
  + `explosion_small/large` (sfx_003) + `pickup_coin` (sfx_001 for
  power-ups) + `confirm` (sfx_014 for power-up-menu) + `death` (sfx_011)
  + `boss_roar` (sfx_012)
- **Music mood:** `track_002 Pressure` (combat loop, driving minor,
  140 BPM) for primary play; `track_005 Approach` (boss theme) for
  bosses.
- **Canonical refs:** `game_011 Gradius`, Galaga-class games.
- **Note:** shmup is **SFX-dense** — ratio sfx:music ~3:1. Weight the
  library heavily toward SFX.

### Action-platformer
- **Channel emphasis:** all 4 channels active. p1 memorable lead + p2
  counter-melody + tri bass + noise drum kit.
- **Recommended sfx:** `jump` (sfx_004) + `land` (sfx_010) +
  `hit_flesh` / `hit_stone` (sfx_005 variants) + `pickup_coin` (sfx_001)
  + `powerup` (sfx_006) + `death` (sfx_011)
- **Music mood:** `track_001 Overture` for title; `track_004 Over the
  Hill` for overworld; `track_005 Approach` for boss. Level themes
  typically 8-16 bars per-world (per SMB3 / MM2 pattern).
- **Canonical refs:** `game_001 SMB3`, `game_007 Mega Man 2`.

### Action-adventure (Zelda-shape)
- **Channel emphasis:** melody-forward (p1 lead); wave channel where
  available for instrument variety. Drums moderate.
- **Recommended sfx:** `pickup_coin` (sfx_001 for rupees) + `confirm`
  (sfx_014 for item-get) + `hit_flesh` (sfx_005 for sword-hits) +
  `break_glass` (sfx_009 for pots) + `powerup` (sfx_006 for heart-
  container) + `error_buzz` (sfx_008 for wrong-item)
- **Music mood:** `track_004 Over the Hill` (overworld) + `track_005
  Approach` (dungeon boss) + `track_009 The Shopkeep` (town). Three-
  register design per note_013 game_013 lesson.
- **Canonical refs:** `game_013 Zelda ALttP`, `game_003 Link's Awakening`.

### Metroidvania
- **Channel emphasis:** similar to action-adventure but with minor-key
  lean + wave channel used for ambient texture. More synth-pad feel.
- **Recommended sfx:** `laser_small` (sfx_002) + `missile` (sfx_013)
  + `powerup` (sfx_006 for ability-gain) + `confirm` (sfx_014 for
  room-clear) + `boss_roar` (sfx_012) + `death` (sfx_011)
- **Music mood:** `track_008 Deep Hollow` (cave / exploration) +
  `track_005 Approach` (boss). Often atmospheric between action
  beats.
- **Canonical refs:** `game_010 Castlevania III`, Super Metroid
  (referenced but not in audio priors; see action_blocks/numerics).

### Fighting (arena)
- **Channel emphasis:** fast p1 lead + aggressive p2 counter +
  driving tri bass + tight noise drums. Syncopation.
- **Recommended sfx:** `hit_flesh` / `hit_metal` / `hit_stone`
  (sfx_005 variants — stacked per attack) + `confirm` (sfx_014 for
  special-move) + `boss_roar` (sfx_012 for taunt) + `death` (sfx_011
  for K.O.)
- **Music mood:** `track_002 Pressure` + `track_005 Approach` for
  final-round intensity.
- **Canonical refs:** `game_008 Street Fighter II` (FM-rich; our 4ch
  approximates the structure not timbre).

### Skater / trick-scorer
- **Channel emphasis:** funk-influenced — slap-like tri bass, p1
  chord-hits, p2 counter-melody. Drum kit very tight.
- **Recommended sfx:** `confirm` (sfx_014 for trick-land) + `land`
  (sfx_010 for ramp-exit) + `error_buzz` (sfx_008 for bail) +
  `pickup_coin` (sfx_001 for letter-pickup)
- **Music mood:** `track_002 Pressure` at 140 BPM is close to the
  THPS tempo range. License-free punk/ska feel needs composition, not
  just chipsynth settings.
- **Canonical refs:** THPS (not in audio priors; noted in
  action_blocks/numerics/coverage_sweep/prompt_015).

### Rhythm
- **Channel emphasis:** drum-forward (noise channel dominant). p1/p2
  carry beatmap notes (timed to audio track). wave may hold root
  drone.
- **Recommended sfx:** `confirm` (sfx_014 for hit) + `error_buzz`
  (sfx_008 for miss) + `pickup_coin` (sfx_001 for streak bonus)
- **Music mood:** `track_002 Pressure` (fast feel) or `track_005
  Approach` (intense). Music IS the game — pick tempo carefully.
- **Canonical refs:** DDR-class, Beatmania. Content-multiplier:
  1 `RhythmTrack` mechanic × N beatmaps.

### Sandbox / life-sim (with sandbox flag)
- **Channel emphasis:** low-energy — tri drone + occasional p1
  phrase. Minimal percussion. wave for timbre flavor.
- **Recommended sfx:** `pickup_coin` (sfx_001) + `confirm` (sfx_014)
  + `menu_blip` (sfx_007 for cursor) + `powerup` (sfx_006 for
  milestone) + `break_glass` (sfx_009 for destructible)
- **Music mood:** `track_007 Idle Hum` (contemplative) + `track_009
  The Shopkeep` (active zone). Day-night cycle can swap these.
- **Canonical refs:** (none in priors; Harvest Moon / Stardew
  adjacent, within action-blocks sandbox-flag scope per note_004).

### Narrative-adjacent / adventure (click-based subset)
- **Channel emphasis:** sparse. Often no drums. p1 + triangle + wave
  carry mood. Long-held notes.
- **Recommended sfx:** `menu_blip` / `confirm` (sfx_007/014 for UI) +
  `error_buzz` (sfx_008 for wrong-action) + `break_glass` (sfx_009
  for puzzle-object state change) + `powerup` (sfx_006 for major-
  story-beat)
- **Music mood:** `track_007 Idle Hum` or `track_009 The Shopkeep`.
  `track_008 Deep Hollow` for mystery/danger scenes.
- **Canonical refs:** Monkey Island (referenced in attempts/attempt_011
  but not in audio priors), `game_015 Cave Story` (hybrid).

### Survival horror / proximity-tension
- **Channel emphasis:** mostly silent. p1 sparse, occasional stings.
  noise for ambient pulses. tri drone.
- **Recommended sfx:** `break_glass` (sfx_009 for crashing objects) +
  `boss_roar` (sfx_012 for threat signal) + `error_buzz` (sfx_008
  hard-variant for alarm) + `hit_flesh` (sfx_005) + `missile` (sfx_013
  for nearby whoosh) + `death` (sfx_011)
- **Music mood:** `track_008 Deep Hollow` (primary). `track_006 Fall`
  (game-over). NO upbeat music in this genre.
- **Canonical refs:** (none in priors; Resident Evil / Silent Hill
  adjacent, within action-blocks real-time-spatial scope).

### Maze-chase (Pac-Man archetype)
- **Channel emphasis:** arcade-custom — 3 channels, simple waveforms.
  Music minimal; SFX dominant.
- **Recommended sfx:** `menu_blip` (sfx_007 for dot-eat alternating) +
  `pickup_coin` (sfx_001 for fruit) + `powerup` (sfx_006 for
  power-pellet) + `error_buzz` (sfx_008 for caught-by-ghost) + `death`
  (sfx_011)
- **Music mood:** **no BGM.** Pac-Man pattern per `game_005 Pac-Man`.
  State-sonification loops replace music (power-pellet siren, hurry-up
  alarm — use `play_sfx_loop` per attempt_002 queue).
- **Canonical refs:** `game_005 Pac-Man`.

### Rhythm-action hybrid (Rez / quantized shooter)
- **Channel emphasis:** base-track p1 + p2 layer always playing;
  gameplay SFX are pitched in-key with the current bar.
- **Recommended sfx:** `laser_small` (sfx_002) + `confirm` (sfx_014
  for lock-on) + `missile` (sfx_013 for lock-on-fire) + `level_up`
  (sfx_016 for section-clear)
- **Music mood:** `track_011 The Clock` (165 BPM driving action)
  or `track_002 Pressure` (140 BPM medium-intensity). Base-track-
  always-playing paradigm: `ChipMusic` with `loop: true` +
  `bpm_driven_by` mechanic-ref when available.
- **Canonical refs:** `game_018 Rez`.
- **Note:** full rhythm-action benefits from v1.1.3 beat-quantize on
  `play_sfx_ref` (flagged in game_018 prior). Without it, standard
  arcade-shooter palette applies.

### Rhythm-roguelite hybrid (NecroDancer)
- **Channel emphasis:** drum-prominent base track (kick on every
  downbeat — player must HEAR the beat). p1 carries floor-theme
  melody.
- **Recommended sfx:** `confirm` (sfx_014 for on-beat move) +
  `error_buzz` (sfx_008 for off-beat miss) + `hit_flesh` (sfx_005
  for combat) + `pickup_coin` (sfx_001 for loot) + `step` (sfx_020
  variants for grid-move confirmation)
- **Music mood:** `track_002 Pressure` for combat floors; `track_005
  Approach` for boss floors. Each track MUST have clear 4-beat kick
  pulse.
- **Canonical refs:** `game_019 Crypt of the NecroDancer`.
- **Note:** audio is LOAD-BEARING for gameplay (not decoration).
  Requires accurate `exposes.current_beat` on `ChipMusic` mechanic
  + v1.1.3 beat-gated triggers.

### Narrative-RPG (overworld-only; battle overlay is separate scaffold)
- **Channel emphasis:** melody-first p1 + harmony p2 + walking
  triangle + sparse drums. Leitmotif composition strategy (shared
  motifs across tracks per character).
- **Recommended sfx:** `confirm` (sfx_014 for dialog-advance) +
  `menu_blip` (sfx_007 for menu) + `pickup_coin` (sfx_001 for items) +
  `heal` (sfx_018) + `powerup` (sfx_006 for ability-gain) +
  `error_buzz` (sfx_008 for refusal) + `level_up` (sfx_016)
- **Music mood:** `track_004 Over the Hill` (overworld) +
  `track_009 The Shopkeep` (town) + `track_008 Deep Hollow`
  (dungeon) + `track_007 Idle Hum` (menu) + `track_012 Triumph`
  (story-victory). Each major character can get a short variant of
  `track_001 Overture`.
- **Canonical refs:** `game_020 Undertale` (overworld + narrative
  layer), `game_013 Zelda ALttP`, `game_014 FF6 overworld`. Full
  JRPG battle system is out-of-action-blocks-scaffold per note_013 —
  those games need the JRPG-battle scaffold when built.

---

## Cross-genre notes

- **Character-theme pattern** (seen in games 002 Chrono, 008 SF2,
  014 FF6): in multi-character games, author one short ChipMusic
  theme per character. Flow selects based on current protagonist
  archetype.

- **Three-register pattern** (Zelda ALttP / game_013 lesson): in
  world-exploration games, use 3 tracks (overworld / dungeon-or-
  danger / town-safe) and let flow switch by scene type. `track_004
  + track_005 + track_009` demonstrate.

- **Boss encounter pattern** (MM2 / SF2 / FF6): short intro sting →
  combat loop → victory sting. Three ChipMusic mechanics in sequence;
  EmbeddedMinigame (when implemented) fits cleanly.

- **State-sonification loops** (Pac-Man / Gradius / Zelda low-
  hearts): looping SFX that replace or augment music for critical
  state signals. Use `play_sfx_loop` (queued attempt_002).

- **Content-multiplier leverage** (note_009): `RhythmTrack`,
  `DialogScript` (via DialogTree), `ProceduralRoomChain` all produce
  many games per one mechanic instantiation. Rhythm games + adventure
  games + roguelites benefit most.

## Coverage gaps

Current palette table covers 11 genres well. Uncovered but in-scope:
- **Racing arcade** (Mario Kart-style) — not in priors yet. Audio palette:
  engine-drone loop (play_sfx_loop candidate), impact stingers, boost
  powerup.
- **Puzzle continuous** (Lemmings, Braid) — hand-placed per v2
  continuous-puzzle expectations. Audio is usually light melodic +
  puzzle-object sfx.
- **Roguelite** (Hades / Isaac) — ProceduralRoomChain-shape. Audio:
  combat loop + room-clear sting + shop-loop. Already well-served by
  existing entries.

Will expand palette_MAP next fire if priors / sfx cover new genres.
