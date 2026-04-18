# Game 016 — Super Mario 64 (1996, Nintendo 64)

**Chip:** no single chip — N64 audio is CPU-driven through a DSP
microcode (either Nintendo's default or game-custom). Effectively
**software MIDI playback with sample-based instruments** + 32 parallel
voices with dynamic assignment.

**Channels:** up to 32 concurrent voices (cart-dependent).

## Why this matters

Mario 64 is the **transition point from chip-era to sample-era**. The
same composer (Koji Kondo, cf. game_001 SMB3) moves from 4-channel
NES constraints to 32-voice sampled playback. The **same
compositional sensibility** (melody-forward, memorable motifs) carries
across a 10x channel-count change.

Validates Kirby's lesson from game_012: **composition trumps chip.**

## Instrument archetypes

General MIDI-ish sample set with N64 DSP tweaks:
- **Strings, brass, woodwinds** — sampled orchestral instruments
- **Choir, sitar, acoustic guitar** — for world-specific flavor
- **Drum kit** — multi-sample kit, much more dynamic range than NES
  noise-channel drums
- **Ambient pads** — for calm/cave/water areas (Dire Dire Docks is
  famous for this)

**Real reverb and chorus** via the DSP effects bus — first time in
the Mario lineage. Compare to Chrono's S-DSP echo (game_002): same
idea, different hardware generation.

## Music style tags

`transition-era`, `32-voice-sample-playback`, `N64-DSP-reverb`,
`orchestral-imitation`, `memorable-per-world`, `melodic-first`,
`ambient-track-variety` (fast / slow / ambient), `composition-
carries-through-chip-change`.

## Signature

**"Bob-omb Battlefield"** — the first real world's theme. A simple
melody with clean 4-bar phrases; despite the leap in hardware, the
structure is recognizably Koji Kondo. **What a composer chooses to
emphasize is more audibly identity-defining than the timbre they
use.**

"Dire Dire Docks" (underwater theme) — the N64 DSP's reverb finally
lets Kondo write long-sustain ambient without timbral fatigue. The
ambient-pad archetype enters the Mario vocabulary.

## Lessons for action-blocks audio

- **Mario 64 is out of chipsynth's direct coverage** — sample-based
  playback with 32 voices is an entirely different system. However:

- **The compositional patterns still apply.** Kondo's melodic approach
  (memorable 4-bar phrases, strong motifs, major-key brightness) is
  orthogonal to the synthesis method. Our chipsynth can author
  Kondo-shape tracks; they'll sound chippy rather than orchestral,
  but the melodic identity carries.

- **Ambient-track-type** (calm, sustained, reverb-heavy) is a class
  we've been addressing (see track_007 "Idle Hum" and track_008 "Deep
  Hollow"). Dire Dire Docks confirms this is a canonical track role,
  not an edge case. Reinforces palette_MAP's "sandbox" and "narrative-
  adjacent" entries.

- **Genre-transition lesson:** as gaming audio hardware evolved, the
  primitives (melody / harmony / bass / percussion) stayed constant.
  Our 4-channel chipsynth is in the same position — constrained
  timbre, unlimited melody. What an author EMITS matters more than
  what the engine PLAYS.
