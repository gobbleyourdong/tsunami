# Game 005 — Pac-Man (1980, arcade)

**Chip:** Namco WSG (Waveform Sound Generator) — custom 3-channel
PSG running at 24 kHz.

**Channels:** 3
- All 3 channels play 32-sample 4-bit waveforms (like GB's wave
  channel, but smaller sample rate and no other channel types).
- Each channel has its own pitch, volume, and waveform slot.

## Waveform archetypes

- Slot 0: basic square-like
- Slot 1: triangle-ish
- Slot 2-7: various smoothed wave shapes producing different timbres
- No dedicated noise channel — percussion approximated via fast
  waveform flips.

**Everything is one synthesis mechanism (table-driven waveform
playback).** Simpler than NES's multi-channel heterogeneity.

## SFX archetypes (the game's audio IS mostly sfx)

Pac-Man's arcade audio is **90% SFX, 10% short stingers**:
- Intro siren: ascending wail (pitch sweep on slot 1)
- Munch-dot: two-note alternating loop (the "waka-waka")
- Eat-fruit: short ascending arpeggio
- Power-pellet active: hurry-up siren (pitch oscillation)
- Eat-ghost: descending cluster (danger-and-reward inversion)
- Death: descending stepped scale with pitch-bend fade
- Life-lost sting: short 3-note minor figure
- Round-clear: major arpeggio + bonus points jingle

## Music style tags

`sfx-first`, `no-background-music`, `siren-motifs`, `minimal-
composition`, `audio-as-status-indicator` (sound tells you game
state — normal / power-up / escape / death).

## Signature

**Audio-as-status-indicator.** Arcade games of this era don't have
"background music" — they have **state sonification.** The player
tells from audio alone whether ghosts are vulnerable, whether the
player is near death, whether a bonus fruit just appeared. Each
sound is a **lightweight notification,** not a composition.

This is a useful precedent for action-blocks audio: **many real-time
spatial games need very little music and a lot of well-placed SFX.**
A good SFX library serves arcade, shooter, survival-horror (sparse
music), and roguelike (mostly-silent dungeon) genres.

## Lessons for action-blocks audio

- **SFX library priority ≥ music library** for arcade-shape games.
  Our content-thread target of 15–30 sfxr seeds may be underscaled
  given how many archetypes arcade audio uses.
- **Pitch-sweep as a primitive** is worth naming in sfxr params.
  Pac-Man's siren, death-fall, eat-ghost are all single-sfx played
  with time-varying pitch. jsfxr's `p_freq_ramp` handles this;
  confirm synthesis thread exposes it.
- **State-sonification loops** (power-pellet siren, hurry-up alarm)
  need a "looping sfx" path — not just one-shots. Synthesis thread
  may want to add `play_sfx_loop` / `stop_sfx_loop` ActionRefs
  separate from one-shot `play_sfx`.
