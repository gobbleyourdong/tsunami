# Game 018 — Rez (2001, PS2/Dreamcast, Tetsuya Mizuguchi)

**Chip:** not a chip-based game. PS2 with custom audio engine.
**Channels:** abstract — music is procedurally layered based on
gameplay.

**Genre:** rhythm-action rail-shooter. Player movement + shots build
the music in real-time.

## Why this matters

Rez is the **canonical "music emerges from gameplay" title.** Player
actions trigger musical events that layer over a base track. Dense
"you-are-the-composer" feedback. One of the most influential
experiments in procedural music-gameplay coupling.

## Instrument archetypes

Electronic / techno — **not chip-tuned** but the structural pattern is
what matters:
- **Base track:** ambient / techno / trance layer, always playing
- **Player-action layers:** shots, lock-on-confirms, enemy-hits all
  add melodic or rhythmic content that **stays in key and in time**
  with the base
- **Layered-reveal tracks:** as the player progresses through a level,
  more layers of the base track are added

## "SFX" (music-integrated events)

- Shot-fire: tonal pulse in-key with current bar
- Lock-on-confirm (when targeting): rising synth
- Target-hit: percussive or melodic hit in rhythm with base
- Lock-on-release (8 shots at once): flurry that fills a rhythmic
  phrase
- Section-clear: crescendo of all accumulated layers
- Boss-phase-shift: music modulates to new key/tempo

## Music style tags

`gameplay-generates-music`, `quantized-to-beat`, `layered-progression`,
`synesthesia`, `techno-trance-base`, `mizuguchi-school`.

## Signature

**Every player action is beat-quantized.** When you pull the trigger,
the shot fires on the next sub-beat — not immediately. This slight
delay is the entire game's core feel. The player IS the composer.

Rez predates "rhythm game" as a common genre; it invented the
**rhythm-action hybrid** that NecroDancer, Hotline Miami's timing
feel, and Thumper would later refine.

## Lessons for action-blocks audio

- **Beat-quantization as a gameplay-music bridge.** Our ChipMusic
  could optionally expose a `current_beat` field (already planned
  per the mechanic's `exposes`). Game actions that fire
  `play_sfx_ref` could snap to next-beat if a quantization flag is
  set:
  ```ts
  { kind: 'play_sfx_ref', library_ref: 'lib', preset: 'shot',
    quantize_to?: 'beat' | 'half' | 'bar' }
  ```
  Flag to synthesis thread as a v1.1.3 candidate — would unlock
  Rez-class rhythm-action games.

- **Layered-reveal tracks.** Dynamic-layer crossfade from game_009
  Shovel Knight partially addresses this. Rez takes it further: 4-8
  layers that accumulate based on progress. Our ChipMusic could
  support `layers: ChipMusicTrack[]` where layer N fades in at
  condition N. Extension of the existing `overlay_condition`
  mechanism.

- **Music-generates-from-player** is a deeper pattern than we've
  modeled. Explicitly out of v1 action-blocks scope (Rez is its own
  scaffold shape), but the infrastructure (beat-quantization + layer-
  fading) is shared.

- Palette_MAP needs a **rhythm-action hybrid** row: base track + SFX-
  quantized-to-beat + layered progression. Add in fire 4 if time.
