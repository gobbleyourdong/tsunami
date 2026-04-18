# Game 003 — The Legend of Zelda: Link's Awakening (1993, Game Boy)

**Chip:** Sharp LR35902 PSG. **Channels:** 4
- **Pulse 1** — sweepable square (can do pitch sweeps in hardware)
- **Pulse 2** — plain square
- **Wave channel** — 32-sample 4-bit custom waveform (programmable!)
  This is GB's signature — any user-defined waveform, looped. Can be
  any timbre from sawtooth to sine to "ocarina-ish."
- **Noise** — pseudorandom at variable clock

## Waveform / instrument archetypes

| Channel | Archetype | Notes |
|---|---|---|
| Pulse 1 | lead (with slides) | uses hw pitch sweep for portamento fills |
| Pulse 2 | chord-arpeggio | fast 3-note arp for chord feel, same as NES |
| Wave | melody / bass | 32-sample table = the richest timbre on-chip |
| Noise | percussion | similar to NES — short burst = snare, long = cymbal |

**Wave channel is the killer feature.** Load a sawtooth sample → it's
a pseudo-sawtooth lead. Load a low-sample-rate sine → mellow. Load a
pulse-like wave → second pulse. Most GB tracks **alternate the wave
channel's sample mid-song** for instrument swaps.

## SFX archetypes

- Item-get: 4-note major arpeggio (classic Zelda sting)
- Sword-slash: noise burst + descending pitch
- Open-chest: ascending arp with wave channel lead
- Enter-cave: downward pitch slide + reverb-less pad
- Overworld → Indoor transition: signature "descent" on wave channel
- Pickup-rupee: short pulse blip with high-to-high interval
- Menu-select: high pulse tick

## Music style tags

`island-narrative`, `major-key-brightness`, `sparse-but-melodic`,
`4ch-constraint-tight`, `percussion-light`, `wave-channel-as-hero`.

## Signature

**Koholint dream-logic** — music feels airy and slightly off-kilter.
Achieved by keeping textures sparse (rarely all 4 channels active),
using major 7ths liberally, and swapping wave channel timbres for
instrument color.

**Composers:** Kazumi Totaka + Minako Hamano + Kozue Ishikawa.

## Lessons for action-blocks audio

- **Wave channel** is a "free" 5th timbre type beyond NES's 4. For
  our chipsynth spec, consider adding an optional `wave` channel
  with a user-defined 32-sample table. Cost is low (OscillatorNode +
  custom PeriodicWave). Big expressivity gain.
- GB soundtracks demonstrate that **4 channels + 1 flex-timbre is
  enough for a full game's worth of varied music.** Our proposed
  2 pulse + triangle + noise hits this target shape.
- The hardware pitch-sweep on Pulse 1 produces "portamento-fill"
  passages that sound distinctive. Worth including in the chipsynth
  spec as `pitch_slide_ms` or similar per-note parameter.
