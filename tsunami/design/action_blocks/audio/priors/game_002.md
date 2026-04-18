# Game 002 — Chrono Trigger (1995, SNES)

**Chip:** Sony SPC700 + S-DSP. **Channels:** 8 ADPCM.
- All 8 channels play **sample-based instruments** (small looped
  recordings compressed via Bit Rate Reduction).
- Pitch, ADSR, pan, echo, vibrato all per-channel.
- S-DSP's 8-tap hardware echo unit is distinctive; many Chrono tracks
  use it for "cavern" / "dream" feel.

## Instrument archetypes

| Channel role | Archetype | Typical instrument |
|---|---|---|
| Melody | warm lead | synth horn, panpipe, ocarina |
| Counter-melody | flute / bell | sampled flute or celesta |
| Pads | sustained strings | synth strings or choir sample |
| Bass | round bass | sampled electric or synth bass |
| Drum kit | multi-sample | kick/snare/hat split across 2–3 channels |
| Ambience | wind / drone | low-volume noise or pad with long echo |

**ADSR range:** much wider than NES — slow attack pads are possible
(e.g., 1.5s attack strings on "Corridor of Time"), which NES can't do.

## SFX archetypes

Chrono leans on **synth stingers** more than sampled SFX:
- Menu-select: 4-note arp bell
- Confirm: bright descending bell
- Cancel: short detuned square
- Damage: short noise burst (sampled)
- Magic-cast: shimmering chord sweep
- Battle-start: signature 4-note motif (leitmotif of the battle theme)

## Music style tags

`atmospheric`, `cinematic`, `leitmotif-per-character`, `pad-heavy`,
`multi-timbral`, `echo-effected`, `key-modulation` (Yasunori Mitsuda
frequently modulates mid-track), `emotional-dynamic-range`.

## Signature

**Character leitmotif system** — each party member has a short
musical phrase (4–8 notes) that appears in multiple tracks. Robo's
theme quotes mechanical patterns; Frog's theme quotes baroque minor.
Emergence from composition: 7 characters × ~30 tracks = hundreds of
thematic echoes without explicit authoring.

**Composers:** Yasunori Mitsuda + Nobuo Uematsu + Noriko Matsueda.

## Lessons for action-blocks audio

- 8-channel sample playback is **way out of scope** for the chipsynth
  spec. Our 4-channel NES-style is the right starting point; SNES-
  style sample playback is a v2 addition (would need a sample-based
  synth instead of wave-based).
- **Echo as a post-FX** is high-leverage — small implementation cost
  (one delay line + feedback), big feel contribution. Worth flagging
  to synthesis thread as an optional ActionRef parameter.
- Leitmotif authoring pattern fits our ChipMusic spec naturally:
  content-multiplier per note_009 — 1 mechanic × N track JSONs with
  shared motifs = pattern library without explicit leitmotif code.
