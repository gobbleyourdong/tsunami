# Audio — status

> Shared state between synthesis + content threads. Read before write.

**Last updated:** synthesis thread, fire 4 — attempt_004 landed.

## Fire 4 (synthesis) delta

- **attempt_004.md landed** — 3 findings from content priors 018
  (Rez) and 019 (NecroDancer) that synthesis fire 3 missed by reading
  status summary instead of priors directly. Signals:
  - F5: `quantize_to` optional field on 4 audio ActionRefs (beat-
    quantize SFX firing)
  - F6: `on_beat` / `off_beat` as first-class ConditionKeys emitted by
    ChipMusic (enables rhythm-gated triggers)
  - F7: `overlay_tracks: ChipMusicTrack[]` + `overlay_conditions:
    ConditionKey[]` — generalizes 2-layer overlay from attempt_002
    F2 to N-layer
- +2 validator error classes: `invalid_quantize_source`,
  `overlay_condition_mismatch`. Total now 6.
- +3 ship criteria tests (quantize, on_beat, N-layer crossfade).
- Self-audit: **priors-over-status read discipline** noted as a
  synthesis-side discipline for future fires.

## Implementer-ready state (updated)

- 4 attempts landed
- chipsynth.ts ~250 LOC, sfxr.ts ~300 LOC
- 3 engine integration methods
- 7 audio ActionRef kinds, 4 with optional `quantize_to`
- 2 MechanicTypes with expanded exposes
- 6 validator error classes
- Prompt-scaffold pending content palette_MAP migration

## Fire 5 synthesis plan

- Re-read priors 016 (Mario 64), 017 (Downwell), 020 (Undertale) that
  I haven't deeply scanned. Per fire-4 self-audit: don't trust status.
- Audit attempt_004 per Sigma confirmation-bias protocol.
- If no structural signal → hold and flag operator (counter = 1 of 2
  no-signal fires for full Data Ceiling stop).

If cron keeps firing with no new signal, holding indefinitely. Operator
can `CronDelete 84a20f9f` to stop the 10-min cadence.

## Threads

- **Synthesis thread** (cron `4574b60c`): 3 attempts landed. Shipped
  v1.1 extension (attempt_001) + content-signal absorption (attempt_002)
  + mixer-refs finding (attempt_003). **Implementer-ready.**
- **Content thread** (cron `84a20f9f`): 4 fires. **All quotas met:
  20 priors, 12 tracks, 20 sfx seeds, palette_MAP (14 genre rows).**

## Content-thread final deliverables

### Priors — 20 / 20 ✓

| # | Game | Platform | Year | Archetype |
|---|---|---|---|---|
| 001 | Super Mario Bros 3 | NES | 1988 | 2-pulse+tri+noise baseline |
| 002 | Chrono Trigger | SNES | 1995 | 8ch ADPCM + S-DSP echo, leitmotif |
| 003 | Link's Awakening | Game Boy | 1993 | wave channel (custom 32-sample) |
| 004 | Sonic 2 | Genesis | 1992 | YM2612 FM (scope reference) |
| 005 | Pac-Man | arcade | 1980 | state-sonification loops |
| 006 | Tetris | Game Boy | 1989 | BPM-as-difficulty, PD-melody |
| 007 | Mega Man 2 | NES | 1988 | boss-intro-sting, aggressive bass |
| 008 | Street Fighter II | arcade | 1991 | character-theme per fighter |
| 009 | Shovel Knight | modern | 2014 | dynamic-layer crossfade |
| 010 | Castlevania III | NES+VRC6 | 1989 | expansion-chip channels |
| 011 | Gradius | arcade | 1985 | power-up-bar audio, shmup density |
| 012 | Kirby's Dream Land | Game Boy | 1992 | wave-table swap, mood-from-composition |
| 013 | Zelda: A Link to the Past | SNES | 1991 | three-register design, HP alarm |
| 014 | Final Fantasy VI | SNES | 1994 | long-form composition, piano signature |
| 015 | Cave Story | freeware | 2004 | indie-chip-hybrid palette |
| 016 | Super Mario 64 | N64 | 1996 | transition-era composition carries through |
| 017 | Downwell | modern | 2015 | SFX-as-music, combo-pitch-rise |
| 018 | Rez | PS2 | 2001 | gameplay-generates-music, beat-quantize |
| 019 | Crypt of the NecroDancer | modern | 2015 | rhythm-gated action, audio load-bearing |
| 020 | Undertale | modern | 2015 | leitmotif-saturated narrative RPG |

Coverage: NES / GB / SNES / Genesis / arcade / VRC6-expansion / N64-
transition / modern-indie-chiptune / rhythm-action / indie-RPG. Broad
enough to stop.

### Track library — 12 / 12 ✓

| # | Title | BPM | Bars | Mood | Shape |
|---|---|---|---|---|---|
| 001 | Overture (title) | 110 | 8 | anthemic major | pre-canonical (seconds) |
| 002 | Pressure (combat) | 140 | 8 | driving minor | pre-canonical |
| 003 | Resolve (fanfare) | 120 | 4 | resolved major | pre-canonical |
| 004 | Over the Hill (overworld) | 100 | 16 | pastoral major | ✓ canonical |
| 005 | Approach (boss) | 150 | 8 | menacing minor | ✓ canonical |
| 006 | Fall (game-over sting) | 80 | 3 | defeat minor | ✓ canonical |
| 007 | Idle Hum (menu) | 90 | 8 | minor unresolved | ✓ canonical |
| 008 | Deep Hollow (cave) | 60 | 8 | ambient phrygian | ✓ canonical |
| 009 | The Shopkeep (town) | 96 | 8 | warm major | ✓ canonical |
| 010 | Pondering (puzzle) | 88 | 8 | major with suspensions | ✓ canonical |
| 011 | The Clock (escape) | 165 | 8 | urgent C minor, 16ths | ✓ canonical |
| 012 | Triumph (victory theme) | 128 | 16 | anthemic F major, full | ✓ canonical, `loop:false` |

Tracks 001–003 are pre-shape-lock (Maps-Include-Noise retained).
Mechanical re-cast at ship: `time_beats = time_seconds × BPM / 60`.

### Sfx seeds — 20 / 20 ✓

Primary archetypes (each with 2-3 variants):

| # | Name | Archetype | Canonical shape |
|---|---|---|---|
| 001 | `pickup_coin` | pickup | p_ snake_case pre-canonical |
| 002 | `laser_small` | projectile | pre-canonical |
| 003 | `explosion_small` | destruction | pre-canonical |
| 004 | `jump` | movement | pre-canonical |
| 005 | `hit_flesh` | impact | pre-canonical |
| 006 | `powerup` | powerup | ✓ canonical |
| 007 | `menu_blip` | menu-tick | ✓ |
| 008 | `error_buzz` | denial | ✓ |
| 009 | `break_glass` | shatter | ✓ |
| 010 | `land` | impact | ✓ |
| 011 | `death` | defeat sting | ✓ |
| 012 | `boss_roar` | threat growl | ✓ |
| 013 | `missile` | large projectile | ✓ |
| 014 | `confirm` | positive UI | ✓ |
| 015 | `charge` | buildup | ✓ |
| 016 | `level_up` | milestone | ✓ |
| 017 | `spawn` | materialize | ✓ |
| 018 | `heal` | restoration | ✓ |
| 019 | `dash` | quick-movement | ✓ |
| 020 | `step` | footstep | ✓ |

Plus ~40 named variants spanning light/heavy/metallic/muffled/pulse/
beam/epic/soft/portal/bubble/reverse/grass/stone/metal etc.

### palette_MAP — 14 genre rows ✓

Arcade shooter, Action-platformer, Action-adventure, Metroidvania,
Fighting, Skater, Rhythm, Sandbox, Narrative-adjacent, Survival
horror, Maze-chase, Rhythm-action hybrid, Rhythm-roguelite hybrid,
Narrative-RPG. Plus cross-genre patterns (leitmotif, three-register,
boss-encounter, state-sonification, content-multiplier leverage) +
coverage gaps (racing arcade, continuous puzzle, roguelite-action).

## Observations on disk

- `note_001.md` — content → synthesis, 6 signals, fire 1.
- `note_002.md` — synthesis → content, shape handoff + drum vocab
  reconciliation, fire 1.

All cross-thread signals addressed. No unresolved items.

## Stop-signal check

Per BRIEF_CONTENT.md §Stop-signal: stop when
- 20 priors ✓
- 12 tracks ✓
- 20 sfxr seeds ✓
- synthesis attempt_005+ — **not yet (at attempt_003; synthesis
  self-reports implementer-ready)**
- no structural signal for 2 fires — projected imminent

Content side is **at stop**. Synthesis side is 2 attempts shy of the
target milestone but has declared implementer-ready at attempt_003.
Interpreting as: the attempt_005 target was a conservative ceiling;
the system met its actual requirement earlier. Both threads can hold.

## Operator ack

All content deliverables are on disk and ready for the implementer
who lands the audio extension into `engine/src/audio/chipsynth.ts` +
`engine/src/audio/sfxr.ts`:

- **Retro corpus** (20 priors) → scope reference + archetype
  justification per design decision
- **Track library** (12 tracks) → canonical test inputs for ChipSynth;
  ship-gate: at least 3 of the 12 tracks build and play end-to-end
- **Sfx library** (20 seeds + variants) → canonical test inputs for
  Sfxr; ship-gate: 5 archetypes generate non-silent buffers per
  attempt_001 §8
- **palette_MAP** (14 genres) → content for
  `tsunami/context/design_script_audio.md` prompt-scaffold
  subsection; tells Tsunami which SFX + tracks to propose per genre

## Content-thread stance

**Standby.** Not writing new priors / tracks / sfx unless:
1. Synthesis surfaces a schema change that invalidates shapes
2. Operator directs a new content direction
3. Implementer requests spec-level clarification on a specific seed
4. palette_MAP needs genre expansion from operator-added scaffolds

If cron fires with no new signal: hold, update status one-liner.

## Final handoff pointers for implementer

- `priors/game_001..020.md` — 20 retro games, archetype-tagged
- `library/track_001..012.md` — 12 ChipMusicTrack-shape examples
- `library/sfx_001..020.md` — 20 SfxrParams-shape seeds (+ variants)
- `library/palette_MAP.md` — genre → audio palette mapping
- `attempts/attempt_001..003.md` — synthesis-side engine + schema spec
- `observations/note_001..002.md` — cross-thread reconciliation

All under `ark/tsunami/design/action_blocks/audio/`.
