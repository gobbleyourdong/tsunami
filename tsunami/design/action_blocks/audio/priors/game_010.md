# Game 010 — Castlevania III: Dracula's Curse (1989 JP / 1990 US, NES+VRC6)

**Chip:** NES 2A03 + **Konami VRC6** expansion chip (cart-based).
**Channels:** 2 pulse + triangle + noise + DPCM (2A03) + **2
additional pulse + 1 sawtooth** (VRC6).

Total: **8 channels** — significantly richer than vanilla NES.

## Why this matters

Castlevania III demonstrates **optional expansion-chip channels** as
a hardware pattern. Cartridges with expansion chips plug into the
Famicom's expansion-audio pins and multiplex into the mixer.

US NES omitted the expansion-audio pins (decision by Nintendo of
America), so US Castlevania III has 5 channels (same as stock NES)
while JP Famicom version has 8. Same game, two audio versions —
direct comparison lets composers hear what the extra channels buy.

## Instrument archetypes (JP VRC6 version)

- **2A03 channels** — same as game_001 (pulse/pulse/triangle/noise/DPCM)
- **VRC6 pulse 1 & 2:** thicker counter-melodies, harmony without
  arpeggio-tricks
- **VRC6 sawtooth:** bright lead or aggressive bass. This channel is
  the signature "Konami sound" — bright, cutting, different from the
  smoother 2A03 pulses.

Konami composers used the sawtooth for organ-like and brass-like
leads. The full 8-channel arrangement lets a track have:
- 1 lead melody
- 2-voice harmony layer
- 1 counter-melody
- Bass + bass-octave
- Drum kit
- Cymbal or shaker fill

Essentially a small orchestra in 8-bit form.

## Music style tags

`konami-era`, `gothic-horror`, `baroque-minor`, `organ-emulation`,
`virtuosic-runs`, `dense-counterpoint`, `cart-expansion-flex`.

## Signature

**"Beginning" (the first-stage theme) has a baroque-era organ feel**
with multi-voice counterpoint that would be impossible on vanilla
NES. The theme is one of the most-covered chiptune pieces — its
density is a direct function of the VRC6's extra channels.

## Lessons for action-blocks audio

- **Expansion-chip channel count** is a clean precedent for
  `ChipMusic.chip_mode`:
  ```ts
  chip_mode?: 'nes_vanilla' | 'nes_vrc6' | 'nes_vrc7' | 'nes_mmc5' | 'nes_n163' | 'gb'
  ```
  `nes_vanilla` = our 4-ch baseline. `nes_vrc6` = +2 pulse + sawtooth.
  `nes_vrc7` = +6 FM operators (Japanese version). `gb` uses wave
  channel. Default to `nes_vanilla` for minimum scope; let the
  author opt into more channels with explicit chip_mode.

  Implementation cost: each mode is additive oscillator configurations
  + channel-count accounting. ~30-60 lines per mode.

- **Two-version audio as design discipline:** a game can ship with
  a minimal audio set + an expanded set. Useful for mobile / low-
  bandwidth variants. Let the ChipMusic track declare a `channels`
  subset — the synth only instantiates channels present in the track.

- **Virtuosic chiptune (game_009, game_010)** raises the ceiling of
  what modern-composed chip music can do. Our chipsynth, if it handles
  8+ channels cleanly, serves both retro-NES and expansion-chiptune.
  If it caps at 4, it serves only the NES-vanilla tier.
