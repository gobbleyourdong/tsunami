# Game 009 — Shovel Knight (2014, Yacht Club Games — Jake Kaufman scoring)

**Chip emulation:** Famicom-style (NES 2A03 + VRC6 expansion).
**Intentionally adheres to NES hardware limits** for authenticity +
small-studio zero-dep aesthetic.

**Channels:** 2 pulse + triangle + noise (2A03) + 2 additional pulse
+ 1 sawtooth (VRC6). Total 6 channels in expanded mode.

## Why this matters

**Shovel Knight is modern chiptune with self-imposed constraints.**
It proves that the 4-6 channel chip-sound archetype is viable in 2014+
games. Critical and commercial success with entirely authored-as-chip
music. Validates our chipsynth's zero-dep, constrained-palette
approach for modern games, not just retro recreations.

Kaufman also did Mighty Switch Force, Cave Story remakes, and Chrono
Chronicles. Modern chiptune composer canon.

## Instrument archetypes

- **Pulse channels (4 total via VRC6):** dense counterpoint possible
- **Triangle:** bass (standard NES)
- **Sawtooth (VRC6 unique):** bright lead for "medieval" warmth
- **Noise:** percussion; often cut to minimal
- **Layered chord voicings:** 4-pulse-channel capacity means real
  3-voice + melody chords without arpeggio-tricks

## Music style tags

`modern-retro`, `melodic-dense`, `medieval-fanfare`, `NES-plus`,
`memorable-motifs`, `per-knight-character-theme` (each boss has a
theme), `nostalgic-but-tight`.

## Signature

**Higher note-density than original NES.** Modern composition
practice applied to 4-6 channel chip = more counter-melody, more
complex chord voicings, more rhythmic variation than 1988 would have
delivered. Proves that the channel-count is NOT the quality ceiling;
the composition is.

Shovel Knight also uses **dynamic layering** — a calm overworld track
adds percussion when enemies appear, strips back when safe. This is
achieved by crossfading between two versions of the same track (not
expansion-chip-specific).

## Lessons for action-blocks audio

- **Dynamic-layer pattern** — ChipMusic mechanic could support a
  primary+overlay track structure:
  ```ts
  interface ChipMusicParams {
    base_track: {...}                    // always playing
    overlay_track?: {...}                // fades in when condition met
    overlay_condition?: ConditionKey     // e.g. 'enemies_nearby'
    crossfade_ms?: number
  }
  ```
  Implementation: two chipsynth instances mixed via GainNode
  crossfade. Existing `AudioEngine` already supports music crossfade;
  re-use that infrastructure.

- **Per-boss theme** pattern (same as SF2, same as Mega Man 2). Three
  games confirm this — worth making it the canonical "multiplayer /
  multi-character / multi-boss" authoring example in the prompt
  scaffold.

- **Expansion-chip channel counts (5-6) are stretch-goal for v1.1.**
  The VRC6 / VRC7 / MMC5 / N163 / FME-7 NES expansion chips each add
  different channel types. For v1.0 we're 4ch NES-vanilla; future
  versions could optionally enable "chip_mode: 'vrc6'" which unlocks
  2 pulse + sawtooth.
