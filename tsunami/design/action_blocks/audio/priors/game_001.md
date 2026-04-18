# Game 001 — Super Mario Bros 3 (1988, NES)

**Chip:** Ricoh 2A03. **Channels:** 5 total
- **Pulse 1** — lead melody (square wave, 12.5% / 25% / 50% / 75% duty cycles)
- **Pulse 2** — harmony / counter-melody (square, same duty set)
- **Triangle** — bass line (fixed triangle wave, no volume control — on/off only)
- **Noise** — drums (short/long mode + freq period)
- **DPCM** — sampled drums or voice (rare in NES, used sparingly)

## Waveform / instrument archetypes

| Channel | Archetype | ADSR | Notes |
|---|---|---|---|
| Pulse 1 | lead | sharp A, med S, short D | 25% duty = classic Mario lead |
| Pulse 2 | harmony | same as P1, usually held notes | 12.5% duty = thinner "arpeggio" |
| Triangle | bass | instant attack, held, no dynamics | plucky feel from note retriggering |
| Noise | drums | sharp A, no S, fast D | periodic short-mode = "snare", long = "hi-hat" |

**Typical arpeggios:** fast 3-note broken chord on P1 for "chord feel" —
can't play true chords, so arp at ~30 Hz cycle.

## SFX archetypes present

- Jump: upward pitch sweep, short (~200ms), square wave
- Coin: high pluck + 1 octave up (~50ms), square, sharp env
- Kick (shell): short noise burst + pitch drop
- Powerup pop: ascending arpeggio fanfare
- 1UP: 4-note major arpeggio
- Fireball: descending pitch sweep + noise
- World-map step: single high blip
- Pause: held chord (P1+P2+Tri)

## Music style tags

`arcade-family`, `march-feel`, `nostalgia-core`, `major-key-first`,
`swing-eighths`, `per-area-theme` (each world has distinct motif),
`short-loops` (8-16 bars before repeat).

## Signature

The "area music" archetype — each world has a 16-bar loop with
strong melodic identity. Overworld (1), underground (2), castle (8),
water (3), athletic (airship). Used as **theme-tagging** for area
retrieval — the player knows where they are from 2 notes of audio.

**Composer:** Koji Kondo.

## Lessons for action-blocks audio

- 2 pulse + triangle + noise is sufficient for 80% of "chippy arcade"
  feel. 4-channel chipsynth spec matches.
- DPCM optional — most NES games got by without, and it's bandwidth-
  heavy. Can defer.
- Triangle-bass-with-retrigger is the key "chippy" signature. Not a
  ramp; a triangle wave with instant attack.
- Duty cycle swaps on pulse channels = free timbre variation without
  adding a channel.
