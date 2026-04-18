# Track 011 — "The Clock" (escape chase / time-pressure)

**Shape:** canonical `ChipMusicTrack`.
**Mood:** urgent, rising-tension, minor, tempo-implying
**BPM:** 165    **Bars:** 8    **Key:** C minor
**Channel layout:** pulse1 = fast sixteenth-note lead (chromatic
fragments), pulse2 = urgent repeated hits on off-beats, triangle =
8th-note walking bass (relentless), noise = drum loop hitting every
8th (runaway feel)
**Serves archetype:** timer-running-out, escape-the-collapsing-
dungeon, chase-sequence, final-boss-phase-3, countdown-to-disaster

## Motif

Fast, relentless rhythm. Sixteenth-note pulse1 lead alternates between
E♭/D/C/B cluster (chromatic tension). Pulse2 hits 16th-note off-beats
with 12.5% duty (piercing). Triangle walks down an octave every 2 bars
for "falling" feel. Noise loop kick-hat-kick-snare at 8th-note
resolution — 32 drum hits per bar.

## JSON (first 2 bars + pattern notation for remaining)

```json
{
  "bpm": 165,
  "loop": true,
  "channels": {
    "pulse1": [
      { "time": 0,    "note": "Eb5","duration": 0.25, "dutyCycle": 0.125 },
      { "time": 0.25, "note": "D5", "duration": 0.25 },
      { "time": 0.5,  "note": "C5", "duration": 0.25 },
      { "time": 0.75, "note": "B4", "duration": 0.25 },
      { "time": 1,    "note": "Eb5","duration": 0.25 },
      { "time": 1.25, "note": "F5", "duration": 0.25 },
      { "time": 1.5,  "note": "Eb5","duration": 0.25 },
      { "time": 1.75, "note": "C5", "duration": 0.25 }
    ],
    "pulse2": [
      { "time": 0.125, "note": "C5", "duration": 0.125, "dutyCycle": 0.125 },
      { "time": 0.375, "note": "C5", "duration": 0.125 },
      { "time": 0.625, "note": "C5", "duration": 0.125 },
      { "time": 0.875, "note": "C5", "duration": 0.125 },
      { "time": 1.125, "note": "D5", "duration": 0.125 },
      { "time": 1.375, "note": "D5", "duration": 0.125 },
      { "time": 1.625, "note": "D5", "duration": 0.125 },
      { "time": 1.875, "note": "D5", "duration": 0.125 }
    ],
    "triangle": [
      { "time": 0,    "note": "C3", "duration": 0.25 },
      { "time": 0.25, "note": "B2", "duration": 0.25 },
      { "time": 0.5,  "note": "Bb2","duration": 0.25 },
      { "time": 0.75, "note": "A2", "duration": 0.25 },
      { "time": 1,    "note": "Ab2","duration": 0.25 },
      { "time": 1.25, "note": "G2", "duration": 0.25 },
      { "time": 1.5,  "note": "F#2","duration": 0.25 },
      { "time": 1.75, "note": "F2", "duration": 0.25 }
    ],
    "noise": [
      { "time": 0,    "note": "kick",        "duration": 0.06, "velocity": 0.9 },
      { "time": 0.25, "note": "hat_closed",  "duration": 0.06 },
      { "time": 0.5,  "note": "kick",        "duration": 0.06, "velocity": 0.85 },
      { "time": 0.75, "note": "snare",       "duration": 0.08 },
      { "time": 1,    "note": "kick",        "duration": 0.06, "velocity": 0.9 },
      { "time": 1.25, "note": "hat_closed",  "duration": 0.06 },
      { "time": 1.5,  "note": "kick",        "duration": 0.06, "velocity": 0.85 },
      { "time": 1.75, "note": "snare",       "duration": 0.08 }
    ]
  },
  "mixer": { "pulse1": 1.0, "pulse2": 0.6, "triangle": 0.85, "noise": 0.8 }
}
```

**Content notes:**
- 2 bars shown. Bars 3–8 repeat the chromatic pattern with triangle
  continuing to descend one full octave across the 8 bars.
- 165 BPM + 16th-note density = 11 note-events per second on pulse1
  alone. This is the densest track in the library — tests the
  chipsynth scheduler at high scheduler load.
- Pair with `track_006 "Fall"` for game-over transition when the
  timer runs out.
- Consider using `ChipMusic.bpm_driven_by` (per game_006 Tetris
  lesson, noted for synthesis attempt_003): track speeds up as timer
  runs down.
