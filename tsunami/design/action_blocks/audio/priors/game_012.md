# Game 012 — Kirby's Dream Land (1992, Game Boy)

**Chip:** Same as game_003 (Sharp LR35902). **Channels:** 4.

Same hardware as Link's Awakening — different musical approach.

## Instrument archetypes

- **Pulse 1:** bright melodic lead, cheerful intervals (lots of 6ths
  and 3rds, bouncy)
- **Pulse 2:** counter-melody that swaps octaves playfully
- **Wave channel:** mid-register "flute-ish" or "bell" timbre —
  essential to the Kirby sound. Many Kirby tracks alternate wave
  tables mid-song for smile-inducing surprise.
- **Noise:** light percussion, often sparse — Kirby tracks often
  skip drums entirely for dream-like feel

## SFX archetypes present

- Kirby-inhale: long sustained tone with rising pitch ramp
- Kirby-exhale: descending whoosh
- Enemy-defeated: bright arpeggio "poof"
- Damage-taken: descending two-note stumble
- Ability-copy: sparkly ascending cluster
- Float: fluttering low-amplitude wavering tone
- Menu-select: friendly high-blip (different from "error" low-blip)
- Stage-clear: triumphant major fanfare

## Music style tags

`sugar-sweet`, `major-key-dominant`, `kid-friendly`, `8-bar-loops`,
`wave-channel-as-flute`, `optimistic-harmonic-voicing`, `bouncy`.

## Signature

**Intentional "cute" chord voicings.** Whereas Zelda LA uses major-
7ths for wistfulness, Kirby uses major-6ths and added-9ths for
brightness. Same hardware, opposite emotional register. Shows that
**the composition choice matters more than the chip** when authoring
mood.

Wave-channel table swaps happen often — 2-3 timbre changes within a
30-second loop is typical. Implementing instance should make wave-
table changes efficient (not a full oscillator rebuild per swap).

**Composers:** Jun Ishikawa + Hirokazu Ando.

## Lessons for action-blocks audio

- Mood is a **composition choice**, not a chip-selection choice.
  Our 4-channel chipsynth can produce Kirby-bright or Zelda-wistful
  depending on chord voicing in the track JSON. This validates
  content-thread's one-chipsynth-many-moods authoring path.
- **Wave-table swap within a track** is a feature to flag. The
  ChipMusic mechanic might want an optional per-channel `wave_table`
  array indexed by time/beat, letting the track author change timbre
  mid-song:
  ```
  wave_table_changes?: Array<{ time: number; table: number[] }>
  ```
  Defer to synthesis attempt_003 if needed.
- **Kirby's SFX palette** is unusually SFX-rich for GB (~20 distinct
  sounds for common player actions). Maps to our target of 20 sfxr
  seeds — one Kirby-like game uses the whole catalog comfortably.
