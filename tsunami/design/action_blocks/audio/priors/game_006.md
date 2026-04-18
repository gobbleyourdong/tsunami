# Game 006 — Tetris (1989, Game Boy — Hirokazu Tanaka scoring)

**Chip:** Sharp LR35902 (same as game_003). **Channels:** 4 (pulse +
pulse + wave + noise).

## Instrument archetypes

Same layout as Link's Awakening but used very differently:
- **Pulse 1:** primary melodic lead (Korobeiniki arrangement)
- **Pulse 2:** counter-melody / harmony
- **Wave channel:** held bass pedal or sustained chord tone
- **Noise:** almost unused — Tetris theme has minimal percussion

## SFX archetypes

- Rotate: short pulse tick
- Move left/right: softer tick (lower pitch)
- Drop (fast): pitch sweep down
- Line-clear: ascending arpeggio (1 line) up to 4-note flourish (Tetris)
- Hard-drop lock: single low thud (noise burst)
- Level-up: bright fanfare stinger
- Game-over: descending melodic phrase

## Music style tags

`folk-melody-adaptation`, `rotational-groove`, `low-complexity-high-
recognition`, `2-voice-harmony`, `dance-meter`, `arrangeable-
stress-free`.

## Signature

**Music drives the tempo of gameplay.** As the speed increases, the
music's BPM increases too — the player experiences rising difficulty
as rising musical tension rather than just faster falling blocks. This
is **state-sonification for pace** (cf. Pac-Man's hurry-up siren, but
continuous).

The specific Korobeiniki arrangement is a folk-tune adaptation; the
cultural resonance is free content. Hirokazu Tanaka picked public-
domain melodies and re-voiced them for 4-channel chip.

## Lessons for action-blocks audio

- **BPM-as-a-mutation-param** is worth flagging to synthesis thread.
  A ChipMusic mechanic should let the drive (time / score / wave_index)
  modulate playback BPM dynamically. This composes with Difficulty
  mechanic's S-curve per attempt_006 / 007.

  Schema suggestion:
  ```ts
  interface ChipMusicParams {
    bpm: number                        // static default
    bpm_driven_by?: MechanicId         // e.g. Difficulty ref
    bpm_range?: [number, number]       // easy → hard mapping
    ...
  }
  ```

- **Public-domain melody adaptation** as an authoring pattern.
  Tsunami emitting a ChipMusic track of Greensleeves / Ode to Joy /
  Turkish March is **free** from copyright perspective — LLM knows
  the melodies, arrangement is generative. Flag as a useful example
  class in the prompt scaffold.

- **Minimal-percussion** design works for contemplative genres
  (puzzle, RPG menu, strategy-pause). The noise channel doesn't have
  to be busy — empty-channel is an authoring choice, not an oversight.
