# Game 007 — Mega Man 2 (1988, NES — Takashi Tateishi scoring)

**Chip:** Same as game_001 (NES 2A03). **Channels:** 5 (2 pulse +
triangle + noise + DPCM).

## Instrument archetypes

Notably different NES usage from Mario:
- **Pulse 1:** aggressive fast-moving lead (sixteenth-note runs common)
- **Pulse 2:** syncopated counter-melody, sometimes rhythmic-hit
- **Triangle:** walking bass (octave jumps, driving feel)
- **Noise:** tight drum kit — kick/snare/hat pattern at full tempo
- **DPCM:** occasional sample (metal-clangs, robot-voice) — used more
  than Mario did

## Music style tags

`rock-influenced`, `driving-tempo`, `chromatic-runs`, `minor-key-
dominant`, `high-energy`, `memorable-hooks-per-level`, `boss-intro-
stinger-per-robot-master`.

## Signature

**Every level has a vocal-hook-quality melody.** "Dr. Wily's Castle,"
"Bubble Man," "Air Man" — each is a 16-bar loop with a shape that
stays in memory. The chip constraints produce sparse arrangements, so
every note carries weight. Tateishi was a studio musician; the melodic
writing is tighter than most NES era.

## Lessons for action-blocks audio

- **Boss-intro-stinger pattern:** a short (2-4 bar) descending or
  ominous phrase plays BEFORE the combat loop starts. Serves as
  "here comes a boss" signaling.
  Authoring: a short `ChipMusic` track with `loop: false` plays as
  an EmbeddedMinigame entry condition? Or simpler — the flow can
  chain two ChipMusic plays: sting-on-enter → loop-on-continue.

- **Aggressive-lead-with-triangle-bass** is a transferable template
  for "combat / danger / boss" feel. Same 4-channel layout (our
  chipsynth spec) can carry it. The track_002 "Pressure" I authored
  is a first pass at this shape.

- **Robot Master encounter pattern** = pre-fight intro sting + boss
  theme + victory stinger on kill. Three ChipMusic mechanics composed
  sequentially. Worth including as a "boss encounter" example in
  the palette_MAP I'll author later.
