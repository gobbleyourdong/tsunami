# Game 014 — Final Fantasy VI (1994, SNES)

**Chip:** Same as game_002 + game_013 (SNES SPC700 + S-DSP).
**Channels:** 8 ADPCM.

## Instrument archetypes

Uematsu's signature SNES arrangement approach:
- **Channel 1 (lead):** often an acoustic-piano sample — rare in NES-
  era composers. Gives FF6 an "orchestra-at-home" feel.
- **Channel 2 (harmony):** sampled strings or choir pad
- **Channel 3 (bass):** sampled electric bass or synth bass
- **Channels 4-5 (harp/woodwind):** for character-theme layering
- **Channels 6-7 (drums):** multi-sample kit (kick/snare/hat/tom split)
- **Channel 8 (atmospheric):** reserved for pad or rare voice sample

**Uematsu emphasizes sustained notes over chop-chop arpeggios** — this
makes his tracks feel slower-tempo even when BPM is high. More pad,
less lead.

## SFX archetypes present

Similar FF-series canon to Chrono:
- Menu-select: 4-note bell arp (same as Chrono — shared asset)
- Confirm: descending bright bell
- Cancel: muted short chord
- Cursor-move: high-pitched blip
- Spell-cast: shimmering cluster (different per spell type)
- Item-use: short major arpeggio
- Battle-start: flash-zoom PCM effect + transition sting
- Victory: signature FF victory fanfare (reused from FF1 onward)
- Game-over: short minor phrase

## Music style tags

`uematsu-era`, `character-theme-per-party-member`, `long-form-
composition` (many FF6 tracks are 2-4 minutes unique before looping),
`orchestral-imitation`, `emotional-pad-forward`, `grand-finale-scale`,
`sampled-piano-signature`.

## Signature

**"Aria di Mezzo Carattere" (the Opera scene, track 28).** Full
leitmotif + sung-vocal emulation via sampled voice — one of the most
ambitious SPC700 tracks ever shipped. Shows the SNES chip could
approach near-orchestral output in 1994.

Evidence of note_009's content-multiplier thesis at ceiling: FF6 has
60+ unique tracks in the OST. Same 8 channels × 60 tracks = emergent
variety from one mechanic (the SPC700 playback).

**Composer:** Nobuo Uematsu.

## Lessons for action-blocks audio

- **Long-form composition is out of chipsynth v1 scope.** Our
  target is 8-16 bar loops; FF6 tracks are 60-120 bars with multiple
  phrases. Implementing instance should confirm scheduler can handle
  tracks of that length without drift (should be fine — Web Audio
  clock is precise).
- **Character-theme pattern** (cf. SF2, Chrono) confirmed again. Third
  genre (arcade fighter, RPG battle, narrative RPG) using this
  pattern. Worth promoting to a canonical authoring example in the
  prompt scaffold.
- **Sampled-piano signature is out of chipsynth scope.** Our 4ch
  synth can't do piano-sample-quality timbres. Fine — FF6-scale audio
  uses pre-made assets (the existing AudioEngine.load path), not
  procedural. Two-path audio (sfxr+chipsynth procedural for generic,
  pre-made files for signature moments) is the right integration.
